import textwrap
from typing import List, Dict


class ConversationManager:
    MAX_OUTPUT_CHARS = 2000

    def __init__(self):
        self.history: List[Dict[str, str]] = []

    def clear(self) -> None:
        self.history.clear()

    def add_user_message(self, content: str) -> None:
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.history.append({"role": "assistant", "content": content})

    def add_tool_result(self, tool_call: dict, output: str, success: bool) -> None:
        truncated_output = self._truncate(output)

        content = (
            f"Context: The last command produced the following output. "
            f"Use this to answer the user's next question if it is relevant.\n"
            f"Status: {'Success' if success else 'Failure'}\n"
            f"Output:\n```\n{truncated_output}\n```"
        )

        self.history.append({"role": "assistant", "content": content})

    @staticmethod
    def _truncate(text: str) -> str:
        return textwrap.shorten(text, width=ConversationManager.MAX_OUTPUT_CHARS, placeholder="\n...[truncated]")

    def get_history(self) -> List[Dict[str, str]]:
        return self.history
