import textwrap
from typing import List, Dict, Optional
from datetime import datetime


class ConversationManager:
    MAX_OUTPUT_CHARS = 2000
    MAX_HISTORY_MESSAGES = 20  # Prevent unbounded growth

    def __init__(self):
        self.history: List[Dict[str, str]] = []
        self._token_estimate = 0

    def clear(self) -> None:
        self.history.clear()
        self._token_estimate = 0

    def add_user_message(self, content: str) -> None:
        self.history.append(
            {
                "role": "user",
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._token_estimate += len(content) // 4
        self._trim_if_needed()

    def add_assistant_message(self, content: str) -> None:
        self.history.append(
            {
                "role": "assistant",
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._token_estimate += len(content) // 4
        self._trim_if_needed()

    def add_tool_result(
        self,
        tool_call: dict,
        output: str,
        success: bool,
        execution_time: Optional[float] = None,
    ) -> None:
        truncated_output = self._truncate(output)

        tool_name = tool_call.get("tool", "unknown")
        tool_args = tool_call.get("args", {})

        # Create more informative context
        context_parts = [
            f"Tool: {tool_name}",
            f"Status: {'Success' if success else 'Failure'}",
        ]

        if execution_time:
            context_parts.append(f"Time: {execution_time:.2f}s")

        if tool_name == "shell_command":
            context_parts.append(f"Command: {tool_args.get('command', 'N/A')}")
        elif tool_name in ("read_file", "write_file"):
            context_parts.append(f"Path: {tool_args.get('path', 'N/A')}")

        context = "\n".join(context_parts)

        content = (
            f"[Tool Execution Result]\n{context}\n\n"
            f"Output:\n```\n{truncated_output}\n```"
        )

        self.history.append(
            {
                "role": "assistant",
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "tool": tool_name,
                    "success": success,
                    "execution_time": execution_time,
                },
            }
        )
        self._token_estimate += len(content) // 4
        self._trim_if_needed()

    def _trim_if_needed(self) -> None:
        if len(self.history) > self.MAX_HISTORY_MESSAGES:
            # Keep system message if present, remove oldest user/assistant pairs
            messages_to_remove = len(self.history) - self.MAX_HISTORY_MESSAGES
            self.history = self.history[messages_to_remove:]
            self._recalculate_tokens()

    def _recalculate_tokens(self) -> None:
        self._token_estimate = sum(
            len(msg.get("content", "")) // 4 for msg in self.history
        )

    @staticmethod
    def _truncate(text: str) -> str:
        if len(text) <= ConversationManager.MAX_OUTPUT_CHARS:
            return text

        # For error messages, prioritize the end (stack traces)
        if "Error" in text or "Exception" in text or "Traceback" in text:
            lines = text.split("\n")
            if len(lines) > 10:
                # Keep first 3 and last 7 lines for errors
                truncated = "\n".join(lines[:3] + ["...[truncated]..."] + lines[-7:])
                return textwrap.shorten(
                    truncated,
                    width=ConversationManager.MAX_OUTPUT_CHARS,
                    placeholder="...[truncated]",
                )

        # For normal output, truncate from the middle
        return textwrap.shorten(
            text,
            width=ConversationManager.MAX_OUTPUT_CHARS,
            placeholder="\n...[truncated]",
        )

    def get_history(self, include_metadata: bool = False) -> List[Dict[str, str]]:
        if include_metadata:
            return self.history.copy()

        # Return clean history without metadata for API calls
        return [
            {"role": msg["role"], "content": msg["content"]} for msg in self.history
        ]

    def get_summary(self) -> Dict[str, any]:
        tool_calls = sum(
            1 for msg in self.history if msg.get("metadata", {}).get("tool")
        )

        return {
            "total_messages": len(self.history),
            "tool_calls": tool_calls,
            "estimated_tokens": self._token_estimate,
            "user_messages": sum(1 for msg in self.history if msg["role"] == "user"),
            "assistant_messages": sum(
                1 for msg in self.history if msg["role"] == "assistant"
            ),
        }
