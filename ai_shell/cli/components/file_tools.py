import os

from ai_shell.core.session import Session
from ai_shell.cli.components.tool_result import ToolResult


class FileTools:
    @staticmethod
    def read_file(session: Session, path: str) -> ToolResult:
        try:
            file_path = os.path.abspath(os.path.join(session.cwd, path))

            if not os.path.isfile(file_path):
                return ToolResult(success=False, output="", error=f"Error: '{path}' is not a file.")

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            return ToolResult(success=True, output=content)

        except PermissionError:
            return ToolResult(success=False, output="", error=f"Error: Permission denied reading '{path}'.")
        except UnicodeDecodeError:
            return ToolResult(
                success=False, output="", error=f"Error: '{path}' is not a text file or has invalid encoding."
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Error reading file: {e}")
