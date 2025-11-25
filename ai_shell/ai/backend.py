import os
import platform
import json
import shlex
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod

from mistralai import Mistral, models
import httpx


@dataclass
class AISuggestion:
    explanation: str
    command: Optional[str] = None
    tool_call: Optional[dict] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class CommandCleaner:
    PROMPTS = ["$", "#", ">", ">>>", "…"]

    @staticmethod
    def clean(cmd: str) -> str:
        cmd = cmd.strip()
        cmd = CommandCleaner._remove_code_fences(cmd)

        if cmd.startswith("`") and cmd.endswith("`") and cmd.count("`") == 2:
            cmd = cmd[1:-1].strip()

        if (cmd.startswith('"') and cmd.endswith('"')) or (
            cmd.startswith("'") and cmd.endswith("'")
        ):
            cmd = cmd[1:-1].strip()

        for prompt in CommandCleaner.PROMPTS:
            if cmd.startswith(prompt + " "):
                cmd = cmd[len(prompt) :].strip()
                break

        cmd = CommandCleaner._normalize_echo_env(cmd)

        if "\n" not in cmd and "#" in cmd:
            try:
                parts = shlex.split(cmd)
                cmd = " ".join(parts)
            except ValueError:
                pass

        return cmd

    @staticmethod
    def _remove_code_fences(cmd: str) -> str:
        if cmd.startswith("```") and cmd.endswith("```"):
            inner = cmd[3:-3].strip()
            if "\n" in inner:
                first, rest = inner.split("\n", 1)
                if first.strip() in ("bash", "sh", "shell", "zsh", "fish"):
                    return rest.strip()
            return inner.strip()
        return cmd

    @staticmethod
    def _normalize_echo_env(cmd: str) -> str:
        try:
            parts = shlex.split(cmd)
            if len(parts) == 2 and parts[0] == "echo" and parts[1].startswith("$"):
                return f"printenv {parts[1][1:]}"
        except ValueError:
            pass
        return cmd


class ResponseParser:
    """Parses LLM responses into structured suggestions."""

    @staticmethod
    def parse(text: str) -> AISuggestion:
        """Parse LLM response text into AISuggestion object."""
        text = text.strip()

        explanation = ""
        command = None
        tool_call = None
        metadata = {}

        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)

        if json_match:
            json_start = json_match.start()
            json_end = json_match.end()

            explanation = text[:json_start].strip()
            json_raw = json_match.group(1).strip()

            try:
                data = json.loads(json_raw)
                tool_call = data

                tool_type = data.get("tool", "")
                args = data.get("args", {})

                if tool_type == "shell_command":
                    raw_cmd = args.get("command", "")
                    cleaned = CommandCleaner.clean(raw_cmd)
                    command = cleaned
                    data["args"]["command"] = cleaned

                elif tool_type == "read_file":
                    command = args.get("path")
                    metadata["operation"] = "read"

                elif tool_type == "write_file":
                    command = args.get("path")
                    content = args.get("content", "")
                    metadata["operation"] = "write"
                    metadata["content_length"] = len(content)

                trailing = text[json_end:].strip()
                if trailing:
                    explanation = f"{explanation}\n\n{trailing}".strip()

            except json.JSONDecodeError as e:
                explanation += f"\n\n[Error parsing tool JSON: {e}]"
                metadata["parse_error"] = str(e)

            return AISuggestion(explanation, command, tool_call, metadata=metadata)

        # Plain text answer (no tool call)
        return AISuggestion(text, metadata={"plain_text": True})


class AIBackendBase(ABC):
    @abstractmethod
    def suggest(
        self, question: str, cwd: str, history: Optional[List[Dict[str, str]]] = None
    ) -> AISuggestion:
        pass


def build_system_prompt() -> str:
    """Build the system prompt for the AI assistant."""
    return """You are SAM — an AI command-line assistant for developers.

Your responsibilities:
• Explain commands clearly and concisely.
• Prefer portable POSIX-friendly commands.
• When a user writes a shell command, assume they want it executed.
• Never ask for confirmation, just run it via the tool call.
• Suggest safe commands (avoid destructive operations like rm -rf /).
• If a tool call to find or read a file fails, your first recovery step should be to list files in the current directory (using `ls -la`) to identify the correct filename or path before trying again. Do not immediately give up.
• Provide small, helpful code snippets when beneficial.
• Use the appropriate tool call format when needed.
• When the user mentions a file, script, or path, prefer using read_file or write_file tools.
• Avoid asking the user to "provide the contents" of a file you could read.
• When you modify a file, use write_file instead of printing the entire file.
• When creating new scripts, choose sensible filenames and use write_file to create them.
• After creating executable scripts, use shell_command to make them executable (chmod +x) and run them when appropriate.

TOOLS AVAILABLE:
1. shell_command → run a shell command
   Format: {"tool": "shell_command", "args": {"command": "<command>"}}

2. read_file → read and display a file's contents
   Format: {"tool": "read_file", "args": {"path": "<file_path>"}}

3. write_file → write content to a file
   Format: {"tool": "write_file", "args": {"path": "<file_path>", "content": "<content>"}}

RESPONSE RULES:
1. First explain what you're doing clearly and briefly.
2. When a tool is helpful, output tool calls inside a JSON code block like:

```json
{"tool": "shell_command", "args": {"command": "ls -la"}}
```

3. If no tool is required, answer normally without any JSON block.
4. Use tools frequently to gather context (read_file) and apply changes (write_file).
5. When editing files, describe the change briefly, then use write_file with the full updated content.
6. When creating scripts, describe what it does, use write_file with complete content, then use shell_command to make it executable and optionally run it.
7. Be proactive: if you can complete a task with tools, do it rather than asking the user to do it manually.

Be concise, correct, and developer-friendly."""


class MistralBackend(AIBackendBase):
    DEFAULT_API_URL = "https://codestral.mistral.ai/v1"
    DEFAULT_MODEL = "codestral-latest"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing MISTRAL_API_KEY. Set it as an environment variable or pass it to the constructor."
            )

        self.model = os.getenv("MISTRAL_MODEL", self.DEFAULT_MODEL)
        self.api_url = os.getenv("MISTRAL_API_URL", self.DEFAULT_API_URL)

        self.client = Mistral(api_key=self.api_key)

    def _context(self, cwd: str) -> str:
        osname = platform.system()
        shell = os.path.basename(os.environ.get("SHELL", "unknown"))
        user = os.environ.get("USER", "unknown")
        return f"OS={osname}, Shell={shell}, User={user}, CWD={cwd}"

    def suggest(
        self,
        question: str,
        cwd: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AISuggestion:
        messages = [{"role": "system", "content": build_system_prompt()}]

        if history:
            messages.extend(history)

        messages.append(
            {"role": "user", "content": f"[{self._context(cwd)}]\n\n{question}"}
        )

        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=1000,
            )

            raw = response.choices[0].message.content
            text = raw if isinstance(raw, str) else json.dumps(raw)

            return ResponseParser.parse(text)

        except models.MistralError as e:
            return AISuggestion(
                f"Error communicating with Mistral API: {e}",
                metadata={"error": "mistral_api_error", "details": str(e)},
            )
        except httpx.RequestError as e:
            return AISuggestion(
                f"Network error communicating with Mistral API: {e}",
                metadata={"error": "network_error", "details": str(e)},
            )
        except Exception as e:
            return AISuggestion(
                f"Unexpected error: {e}",
                metadata={"error": "unexpected_error", "details": str(e)},
            )


class AIBackend:
    SUPPORTED_PROVIDERS = ["mistral"]

    def __init__(self, provider: str = "mistral", api_key: Optional[str] = None):
        provider = provider.lower()

        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{provider}'. "
                f"Supported providers: {', '.join(self.SUPPORTED_PROVIDERS)}"
            )

        if provider == "mistral":
            self.backend = MistralBackend(api_key)
        else:
            raise NotImplementedError(f"Provider '{provider}' not yet implemented")

    def suggest(
        self, question: str, cwd: str, history: Optional[List[Dict[str, str]]] = None
    ) -> AISuggestion:
        """Get AI suggestion using the configured backend."""
        return self.backend.suggest(question, cwd, history)
