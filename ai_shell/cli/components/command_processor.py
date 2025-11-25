import json
import time
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.live import Live

from ai_shell.ai.backend import AIBackend, AISuggestion
from ai_shell.core.session import Session
from ai_shell.core.settings import Settings
from ai_shell.execution.safe_executor import run_safe_command
from ai_shell.cli.components.conversation_manager import ConversationManager
from ai_shell.cli.components.output_formatter import OutputFormatter
from ai_shell.cli.components.tool_executor import ToolExecutor
from ai_shell.cli.components.thinking_log import ThinkingLog


class ProcessingState(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    EXECUTING_TOOL = "executing_tool"
    HANDLING_ERROR = "handling_error"
    ANALYZING = "analyzing"


@dataclass
class ToolExecutionResult:
    success: bool
    output: str
    error: Optional[str]
    execution_time: float
    tool_name: str


class CommandProcessor:
    MAX_TOOL_CALLS_PER_QUERY = 5
    MAX_ERROR_RECOVERY_DEPTH = 2  # Prevent infinite error recovery loops

    def __init__(
        self,
        console: Console,
        session: Session,
        settings: Settings,
        conversation: ConversationManager,
    ):
        self.console = console
        self.session = session
        self.settings = settings
        self.conversation = conversation

        self._state = ProcessingState.IDLE
        self._tool_calls_remaining = self.MAX_TOOL_CALLS_PER_QUERY
        self._error_recovery_depth = 0

    def _reset_counters(self) -> None:
        self._tool_calls_remaining = self.MAX_TOOL_CALLS_PER_QUERY
        self._error_recovery_depth = 0

    def _get_backend(self) -> AIBackend:
        return AIBackend(self.settings.provider, self.settings.api_key)

    def _execute_tool_with_timing(
        self, tool_call: dict, suggestion: AISuggestion, silent: bool = False
    ) -> ToolExecutionResult:
        tool_name = tool_call.get("tool", "unknown")

        if not silent and suggestion.command:
            if tool_name == "shell_command":
                OutputFormatter.print_command(self.console, suggestion.command)
            elif tool_name == "read_file":
                OutputFormatter.print_reading_file(self.console, suggestion.command)
            elif tool_name == "write_file":
                args = tool_call.get("args", {})
                content = args.get("content", "")
                size = len(content.encode("utf-8")) if content else None
                OutputFormatter.print_writing_file(
                    self.console, suggestion.command, size
                )

        start_time = time.time()

        with self.console.status(f"Executing {tool_name}..."):
            result = ToolExecutor.execute(
                self.session, tool_call, self.settings.safety_profile
            )

        execution_time = time.time() - start_time
        output = result.output if result.success else result.error
        
        if not silent:
            OutputFormatter.print_output(
                self.console, output, result.success, execution_time
            )

        return ToolExecutionResult(
            success=result.success,
            output=result.output,
            error=result.error,
            execution_time=execution_time,
            tool_name=tool_name,
        )

    def _add_suggestion_to_history(
        self, suggestion: AISuggestion, include_tool: bool = True
    ) -> None:
            assistant_content = suggestion.explanation
            self.conversation.add_assistant_message(assistant_content)

    def _should_execute_tool(self) -> tuple[bool, Optional[str]]:
        if self._tool_calls_remaining <= 0:
            reason = (
                f"Tool call limit reached ({self.MAX_TOOL_CALLS_PER_QUERY} calls). "
                "This prevents infinite loops."
            )
            return False, reason

        return True, None

    def _handle_tool_limit_reached(self) -> None:
        message = (
            f"Tool call limit reached ({self.MAX_TOOL_CALLS_PER_QUERY} calls per query). "
            "Responding without executing further tools."
        )
        OutputFormatter.print_warning(self.console, message)

    def _get_ai_suggestion(
        self, prompt: str, status_message: Optional[str] = "Thinking..."
    ) -> Optional[AISuggestion]:
        try:
            if status_message:
                with self.console.status(status_message):
                    backend = self._get_backend()
                    suggestion = backend.suggest(
                        prompt, self.session.cwd, history=self.conversation.get_history()
                    )
            else:
                backend = self._get_backend()
                suggestion = backend.suggest(
                    prompt, self.session.cwd, history=self.conversation.get_history()
                )
            return suggestion

        except Exception as e:
            OutputFormatter.print_error(
                self.console, "Failed to get AI suggestion", exception=e
            )
            return None

    def _handle_error_with_ai(self, context: str, original_query: str) -> None:
        """Simplified error handler for direct commands."""
        if self._error_recovery_depth >= self.MAX_ERROR_RECOVERY_DEPTH:
            OutputFormatter.print_warning(self.console, "Max error recovery depth reached.")
            return
            
        self._error_recovery_depth += 1
        
        suggestion = self._get_ai_suggestion(context, "Analyzing error...")

        if not suggestion:
            return

        if suggestion.explanation:
            OutputFormatter.print_explanation(self.console, suggestion.explanation)

        self._add_suggestion_to_history(suggestion)

        if suggestion.tool_call:
            can_execute, reason = self._should_execute_tool()
            if not can_execute:
                OutputFormatter.print_info(self.console, reason)
                return

            self._tool_calls_remaining -= 1
            self._execute_tool_with_timing(suggestion.tool_call, suggestion)


    def _build_error_context(self, tool_call: dict, error_output: str) -> str:
        return (
            "The following tool call failed.\n\n"
            f"**Tool call:**\n```json\n{json.dumps(tool_call, indent=2)}\n```\n\n"
            f"**Error output:**\n```\n{error_output}\n```\n\n"
            "Explain what went wrong and suggest a corrected approach. "
            "Consider alternative tools or commands if appropriate."
        )

    def process_direct_command(self, command: str) -> None:
        self._reset_counters()
        self._state = ProcessingState.EXECUTING_TOOL

        try:
            exec_result = self._execute_tool_with_timing(
                {"tool": "shell_command", "args": {"command": command}},
                AISuggestion(explanation="", command=command)
            )

            self.conversation.add_user_message(f"!{command}")
            self.conversation.add_tool_result(
                {"tool": "shell_command", "args": {"command": command}},
                exec_result.output,
                exec_result.success,
                exec_result.execution_time
            )

            if not exec_result.success:
                context = self._build_error_context(
                    {"tool": "shell_command", "args": {"command": command}},
                    exec_result.error
                )
                self._handle_error_with_ai(context, f"!{command}")

        finally:
            self._state = ProcessingState.IDLE

    def process_ai_query(self, query: str) -> None:
        self._reset_counters()
        self._state = ProcessingState.PROCESSING
        self.conversation.add_user_message(query)

        log = ThinkingLog()
        final_explanation = ""
        current_prompt = query

        with Live(log, console=self.console, transient=True, vertical_overflow="visible") as live:
            while self._tool_calls_remaining > 0:
                suggestion = self._get_ai_suggestion(current_prompt, status_message=None)

                if not suggestion:
                    log.add("✗ AI backend failed to produce a suggestion.")
                    break

                if suggestion.explanation:
                    # Log intermediate thoughts, but don't display full panel
                    explanation_summary = suggestion.explanation.split('\n')[0]
                    log.add(f"… {explanation_summary}")

                self.conversation.add_assistant_message(suggestion.explanation)

                if not suggestion.tool_call:
                    final_explanation = suggestion.explanation
                    break

                can_execute, reason = self._should_execute_tool()
                if not can_execute:
                    final_explanation = f"Stopping: {reason}"
                    break
                
                self._tool_calls_remaining -= 1

                tool_name = suggestion.tool_call.get("tool", "unknown").replace('_', ' ').capitalize()
                command_str = suggestion.command or ""
                log_msg = f"{tool_name}: `{command_str}`"
                
                log.add(f"→ {log_msg}")

                exec_result = self._execute_tool_with_timing(
                    suggestion.tool_call, suggestion, silent=True
                )

                self.conversation.add_tool_result(
                    suggestion.tool_call,
                    exec_result.output if exec_result.success else exec_result.error,
                    exec_result.success,
                    exec_result.execution_time,
                )

                if exec_result.success:
                    log.update_last(f"✓ {log_msg}")
                    current_prompt = "Tool executed successfully. Analyze results and proceed."
                else:
                    log.update_last(f"✗ {log_msg}")
                    if exec_result.error:
                        log.add(f"  └─ Error: {exec_result.error.strip()}")
                    
                    current_prompt = self._build_error_context(
                        suggestion.tool_call, exec_result.error
                    )

                    self._error_recovery_depth += 1
                    if self._error_recovery_depth >= self.MAX_ERROR_RECOVERY_DEPTH:
                        final_explanation = "Max error recovery depth reached. Aborting."
                        log.add(f"✗ {final_explanation}")
                        break
        
        if self._tool_calls_remaining <= 0:
            final_explanation = "Tool call limit reached. Aborting."
            log.add(f"✗ {final_explanation}")

        log.complete()

        if final_explanation:
            OutputFormatter.print_explanation(self.console, final_explanation)

        self._state = ProcessingState.IDLE


    def get_state(self) -> ProcessingState:
        return self._state

    def get_remaining_tool_calls(self) -> int:
        return self._tool_calls_remaining
