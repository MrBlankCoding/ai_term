import os
import platform
import json
import shlex
from dataclasses import dataclass
from typing import Optional, List, Dict

from mistralai import Mistral, models
import httpx

@dataclass
class AISuggestion:
    explanation: str
    command: Optional[str] = None
    tool_call: Optional[dict] = None


class CommandCleaner:
    @staticmethod
    def clean(cmd: str) -> str:
        """Clean and normalize a command string."""
        cmd = cmd.strip()

        # Remove code fences
        if cmd.startswith("```") and cmd.endswith("```"):
            inner = cmd[3:-3].strip()
            if "\n" in inner:
                first, rest = inner.split("\n", 1)
                if first.strip() in ("bash", "sh", "shell"):
                    cmd = rest.strip()
                else:
                    cmd = inner.strip()

        # Remove inline backticks
        if cmd.startswith("`") and cmd.endswith("`"):
            cmd = cmd[1:-1].strip()

        # Remove wrapping quotes
        if ((cmd.startswith('"') and cmd.endswith('"')) or 
                (cmd.startswith("'") and cmd.endswith("'"))):
            cmd = cmd[1:-1].strip()

        # Remove shell prompt
        if cmd.startswith("$ "):
            cmd = cmd[2:].strip()

        # Normalize simple env var echo
        try:
            parts = shlex.split(cmd)
            if len(parts) == 2 and parts[0] == "echo" and parts[1].startswith("$"):
                return f"printenv {parts[1][1:]}"
        except ValueError:
            pass

        return cmd


class ResponseParser:
    @staticmethod
    def parse(text: str) -> AISuggestion:
        """Parse LLM response text into AISuggestion object."""
        text = text.strip()

        explanation = ""
        command = None
        tool_call = None

        # Detect JSON tool call
        json_start = text.find("```json")
        if json_start != -1:
            json_end = text.find("```", json_start + 7)
            if json_end != -1:
                explanation = text[:json_start].strip()
                json_raw = text[json_start + 7 : json_end].strip()

                try:
                    data = json.loads(json_raw)
                    tool_call = data

                    # Shell tool
                    if data.get("tool") == "shell_command":
                        raw_cmd = data.get("args", {}).get("command", "")
                        cleaned = CommandCleaner.clean(raw_cmd)
                        command = cleaned
                        data["args"]["command"] = cleaned

                    # Read file tool
                    if data.get("tool") == "read_file":
                        command = data.get("args", {}).get("path")
                    
                    # Write file tool
                    if data.get("tool") == "write_file":
                        command = data.get("args", {}).get("path")

                except json.JSONDecodeError as e:
                    explanation += f"\n\n[Error parsing tool JSON: {e}]"

                return AISuggestion(explanation, command, tool_call)

        # Plain text answer
        return AISuggestion(text)

def build_system_prompt() -> str:
    return """
You are SAM — an AI command-line assistant for developers.

Your responsibilities:
• Explain commands clearly and concisely.
• Prefer portable POSIX-friendly commands.
• When a user writes a shell command, assume they want it executed.
• Never ask for confirmation, just run it via the tool call.
• Suggest safe commands (avoid destructive operations).
• Provide small, helpful code snippets when beneficial.
• Use the appropriate tool call format when needed.
• When the user mentions a file, script, or path (like "my get_weather.sh script"), prefer using the read_file or write_file tools instead of asking the user to paste the contents.
• Avoid asking the user to "provide the contents" of a file that you could read with the tools.
• When you modify a file or script, prefer applying the change via the write_file tool rather than printing the entire updated file contents back to the user.

TOOLS AVAILABLE:
1. shell_command → run a command
2. read_file → read and show a file's contents
3. write_file → write content to a file.
   Format: {"tool": "write_file", "args": {"path": "<file_path>", "content": "<content_to_write>"}}

RESPONSE RULES:
1. First explain what you're doing.
2. When a tool is helpful, output tool calls inside a JSON code block like:

```json
{"tool": "shell_command", "args": {"command": "ls -la"}}
```

3. If no tool is required, answer normally with no JSON block.
4. Prefer using tools frequently to gather context (e.g., read_file) and apply changes (write_file), rather than asking the user to manually supply that information.
5. When editing a file, describe the change briefly in natural language, then use a write_file tool call with the full updated file content instead of pasting the whole file in the explanation.

Be concise, correct, and developer-friendly.
    """


class MistralBackend:
    DEFAULT_API_URL = "https://codestral.mistral.ai/v1"
    DEFAULT_MODEL = "codestral-latest"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("Missing MISTRAL_API_KEY.")

        self.model = os.getenv("MISTRAL_MODEL", self.DEFAULT_MODEL)
        self.api_url = os.getenv("MISTRAL_API_URL", self.DEFAULT_API_URL)

        self.client = Mistral(api_key=self.api_key)

    def _context(self, cwd: str) -> str:
        """Get system context information."""
        osname = platform.system()
        shell = os.path.basename(os.environ.get("SHELL", "unknown"))
        return f"OS={osname}, Shell={shell}, CWD={cwd}"

    def suggest(
        self,
        question: str,
        cwd: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AISuggestion:
        messages: List[MessagesTypedDict] = [
            {"role": "system", "content": build_system_prompt()}
        ]

        if history:
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({
            "role": "user",
            "content": f"[{self._context(cwd)}]\n\n{question}"
        })

        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=800,
            )

            raw = response.choices[0].message.content
            text = raw if isinstance(raw, str) else json.dumps(raw)

            return ResponseParser.parse(text)

        except models.MistralError as e:
            return AISuggestion(f"Error communicating with Mistral API: {e}")
        except httpx.RequestError as e:
            return AISuggestion(
                f"Network error communicating with Mistral API: {e}"
            )


class AIBackend:
    def __init__(self, provider: str = "mistral", api_key: Optional[str] = None):
        provider = provider.lower()
        if provider != "mistral":
            raise ValueError("Only 'mistral' provider is supported currently.")

        self.backend = MistralBackend(api_key)

    def suggest(self, question: str, cwd: str, history=None) -> AISuggestion:
        """Get AI suggestion using the configured backend."""
        return self.backend.suggest(question, cwd, history)
