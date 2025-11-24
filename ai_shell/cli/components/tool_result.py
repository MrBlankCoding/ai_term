from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""
