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

    @staticmethod
    def write_file(session: Session, path: str, content: str) -> ToolResult:
        try:
            file_path = os.path.abspath(os.path.join(session.cwd, path))

            # Security check: ensure the path is within the sandbox
            common_path = os.path.commonpath([session.sandbox_root, file_path])
            if common_path != session.sandbox_root:
                return ToolResult(success=False, output="", error=f"Error: Attempt to write outside of sandbox to '{path}'.")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(success=True, output=f"Successfully wrote to {path}")

        except Exception as e:
            return ToolResult(success=False, output="", error=f"Error writing to file: {e}")