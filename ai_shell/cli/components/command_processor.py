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

    def process_direct_command(self, command: str) -> None:
        with self.console.status("Executing..."):
            ok, _, stdout, stderr = run_safe_command(self.session, command, self.settings.safety_profile)

        output = stdout if ok else stderr
        OutputFormatter.print_output(self.console, output, ok)

        self.conversation.add_user_message(f"!{command}")

        tool_call = {"tool": "shell_command", "args": {"command": command}}
        self.conversation.add_tool_result(tool_call, output, ok)

    def process_ai_query(self, query: str) -> None:
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

            result = ToolExecutor.execute(self.session, suggestion.tool_call, self.settings.safety_profile)

            output = result.output if result.success else result.error
            OutputFormatter.print_output(self.console, output, result.success)

            self.conversation.add_tool_result(suggestion.tool_call, output, result.success)
