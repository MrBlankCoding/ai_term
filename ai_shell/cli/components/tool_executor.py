from rich.console import Console
from ai_shell.cli.components.command_recognizer import CommandRecognizer
from ai_shell.core.session import Session
from ai_shell.execution.safe_executor import run_safe_command
from ai_shell.cli.components.file_tools import FileTools
from ai_shell.cli.components.tool_result import ToolResult


class ToolExecutor:
    @staticmethod
    def execute(session: Session, tool_call: dict, safety_profile: str, recognizer: 'CommandRecognizer' = None, console: Console = None) -> ToolResult:
        tool_name = tool_call.get("tool")
        tool_args = tool_call.get("args", {})

        if tool_name == "read_file":
            path = tool_args.get("path", "")
            return FileTools.read_file(session, path)

        elif tool_name == "shell_command":
            command = tool_args.get("command", "")
            if not command:
                return ToolResult(success=False, output="", error="Error: No command provided")

            ok, _, stdout, stderr = run_safe_command(session, command, safety_profile, recognizer=recognizer, console=console)

            return ToolResult(success=ok, output=stdout if ok else stderr)

        elif tool_name == "write_file":
            path = tool_args.get("path", "")
            content = tool_args.get("content", "")
            if not path:
                return ToolResult(success=False, output="", error="Error: No path provided for write_file")
            return FileTools.write_file(session, path, content)

        else:
            return ToolResult(success=False, output="", error=f"Error: Unknown tool '{tool_name}'")
