import json
from rich.console import Console

from ai_shell.ai.backend import AIBackend
from ai_shell.core.session import Session
from ai_shell.core.settings import Settings
from ai_shell.execution.safe_executor import run_safe_command
from ai_shell.cli.components.conversation_manager import ConversationManager
from ai_shell.cli.components.output_formatter import OutputFormatter
from ai_shell.cli.components.tool_executor import ToolExecutor


class CommandProcessor:
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
        self._handling_error = False
        self.MAX_TOOL_CALLS_PER_QUERY = 5
        self._tool_calls_remaining = self.MAX_TOOL_CALLS_PER_QUERY

    def _handle_error_with_ai(self, context: str) -> None:
        if self._handling_error:
            return

        self._handling_error = True
        try:
            with self.console.status("Analyzing error..."):
                backend = AIBackend(self.settings.provider, self.settings.api_key)
                suggestion = backend.suggest(context, self.session.cwd, history=self.conversation.get_history())

            if suggestion.explanation:
                OutputFormatter.print_explanation(self.console, suggestion.explanation)

            assistant_content = suggestion.explanation
            if suggestion.tool_call:
                assistant_content += f"\n```json\n{json.dumps(suggestion.tool_call)}\n```"
            self.conversation.add_assistant_message(assistant_content)

            if suggestion.tool_call:
                if suggestion.command:
                    tool_name = suggestion.tool_call.get("tool")
                    if tool_name == "shell_command":
                        OutputFormatter.print_command(self.console, suggestion.command)
                    elif tool_name == "read_file":
                        OutputFormatter.print_reading_file(self.console, suggestion.command)
                    elif tool_name == "write_file":
                        OutputFormatter.print_writing_file(self.console, suggestion.command)

                if self._tool_calls_remaining > 0:
                    self._tool_calls_remaining -= 1
                    with self.console.status("Executing command..."):
                        result = ToolExecutor.execute(self.session, suggestion.tool_call, self.settings.safety_profile)

                    output = result.output if result.success else result.error
                    OutputFormatter.print_output(self.console, output, result.success)

                    self.conversation.add_tool_result(suggestion.tool_call, output, result.success)
                else:
                    note = "[Tool limit reached: responding without executing further tools.]"
                    OutputFormatter.print_explanation(self.console, note)
        finally:
            self._handling_error = False

    def _followup_after_tool(self, user_query: str, tool_call: dict, tool_output: str) -> None:
        """Ask the AI to respond in plain text using the tool output, with no further tools."""
        with self.console.status("Analyzing results..."):
            backend = AIBackend(self.settings.provider, self.settings.api_key)
            question = (
                "You just used a tool to help answer the user's request.\n"
                f"Original user request:\n{user_query}\n\n"
                f"Tool call (JSON):\n{json.dumps(tool_call)}\n\n"
                f"Tool output:\n```\n{tool_output}\n```\n\n"
                "Now respond directly to the user in plain text, without proposing or using any further tool calls. "
                "Explain what you learned from the tool output and answer the request."
            )

            suggestion = backend.suggest(question, self.session.cwd, history=self.conversation.get_history())

        if suggestion.explanation:
            OutputFormatter.print_explanation(self.console, suggestion.explanation)

            assistant_content = suggestion.explanation
            if suggestion.tool_call:
                assistant_content += f"\n```json\n{json.dumps(suggestion.tool_call)}\n```"
            self.conversation.add_assistant_message(assistant_content)

    def process_direct_command(self, command: str) -> None:
        with self.console.status("Executing..."):
            ok, _, stdout, stderr = run_safe_command(self.session, command, self.settings.safety_profile)

        output = stdout if ok else stderr
        OutputFormatter.print_output(self.console, output, ok)

        self.conversation.add_user_message(f"!{command}")

        tool_call = {"tool": "shell_command", "args": {"command": command}}
        self.conversation.add_tool_result(tool_call, output, ok)

        if not ok:
            self._tool_calls_remaining = self.MAX_TOOL_CALLS_PER_QUERY
            context = (
                f"The following shell command failed.\n"
                f"Command: {command}\n"
                f"Error output:\n{stderr}\n"
                f"Explain what went wrong and suggest a corrected command."
            )
            self._handle_error_with_ai(context)

    def process_ai_query(self, query: str) -> None:
        # Reset tool budget for this user query
        self._tool_calls_remaining = self.MAX_TOOL_CALLS_PER_QUERY

        with self.console.status("Thinking..."):
            backend = AIBackend(self.settings.provider, self.settings.api_key)
            suggestion = backend.suggest(query, self.session.cwd, history=self.conversation.get_history())

        if suggestion.explanation:
            OutputFormatter.print_explanation(self.console, suggestion.explanation)

        self.conversation.add_user_message(query)

        assistant_content = suggestion.explanation
        if suggestion.tool_call:
            assistant_content += f"\n```json\n{json.dumps(suggestion.tool_call)}\n```"
        self.conversation.add_assistant_message(assistant_content)

        if suggestion.tool_call:
            if suggestion.command:
                tool_name = suggestion.tool_call.get("tool")
                if tool_name == "shell_command":
                    OutputFormatter.print_command(self.console, suggestion.command)
                elif tool_name == "read_file":
                    OutputFormatter.print_reading_file(self.console, suggestion.command)
                elif tool_name == "write_file":
                    OutputFormatter.print_writing_file(self.console, suggestion.command)

            if self._tool_calls_remaining > 0:
                self._tool_calls_remaining -= 1
                with self.console.status("Executing command..."):
                    result = ToolExecutor.execute(self.session, suggestion.tool_call, self.settings.safety_profile)

                output = result.output if result.success else result.error
                OutputFormatter.print_output(self.console, output, result.success)

                self.conversation.add_tool_result(suggestion.tool_call, output, result.success)

                if not result.success:
                    context = (
                        "The following tool call failed.\n"
                        f"Tool call: {json.dumps(suggestion.tool_call)}\n"
                        f"Error output:\n{output}\n"
                        "Explain what went wrong and suggest how to fix it."
                    )
                    self._handle_error_with_ai(context)
                else:
                    # On success, ask the AI to follow up in plain text using the tool output.
                    self._followup_after_tool(query, suggestion.tool_call, output)
            else:
                note = "[Tool limit reached: responding without executing further tools.]"
                OutputFormatter.print_explanation(self.console, note)
