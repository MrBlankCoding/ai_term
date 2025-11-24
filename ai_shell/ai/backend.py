import os
import platform
import json
import shlex
import requests
from typing import Optional, Any
from dataclasses import dataclass


@dataclass
class AISuggestion:
    explanation: str
    command: Optional[str] = None
    tool_call: Optional[dict] = None


class CommandCleaner:
    @staticmethod
    def clean(cmd: str) -> str:
        cmd = cmd.strip()
        
        # Remove code block markers
        if cmd.startswith("```") and cmd.endswith("```") and len(cmd) >= 6:
            cmd = cmd[3:-3].strip()
            # Remove language identifier if present
            if '\n' in cmd:
                first_line, rest = cmd.split('\n', 1)
                if first_line.strip() in ('bash', 'sh', 'shell'):
                    cmd = rest.strip()
        
        # Remove backticks
        if cmd.startswith("`") and cmd.endswith("`") and len(cmd) >= 2:
            cmd = cmd[1:-1].strip()
        
        # Remove quotes
        if len(cmd) >= 2 and ((cmd.startswith('"') and cmd.endswith('"')) or 
                              (cmd.startswith("'") and cmd.endswith("'"))):
            cmd = cmd[1:-1].strip()
        
        # Remove shell prompt prefix
        if cmd.startswith("$ "):
            cmd = cmd[2:].lstrip()
        
        # Convert echo $VAR to printenv VAR for better compatibility
        try:
            parts = shlex.split(cmd)
            if len(parts) == 2 and parts[0] == "echo" and parts[1].startswith("$"):
                var_name = parts[1][1:]
                return f"printenv {var_name}"
        except ValueError:
            pass  # Keep original if parsing fails
        
        return cmd


class ResponseParser:
    @staticmethod
    def parse(text: str) -> AISuggestion:
        """Parse AI response text into an AISuggestion object."""
        explanation = ""
        command: Optional[str] = None
        tool_call: Optional[dict] = None
        
        # Look for JSON tool call
        json_start = text.find("```json")
        if json_start != -1:
            json_end = text.rfind("```", json_start + 7)
            if json_end > json_start:
                explanation = text[:json_start].strip()
                json_block = text[json_start + 7:json_end].strip()
                
                try:
                    tool_call = json.loads(json_block)
                    
                    # Extract and clean command if present
                    if tool_call and tool_call.get("tool") == "shell_command":
                        command = tool_call.get("args", {}).get("command")
                        if command:
                            command = CommandCleaner.clean(command)
                            tool_call["args"]["command"] = command
                    
                    # Extract path for read_file tool
                    elif tool_call and tool_call.get("tool") == "read_file":
                        path = tool_call.get("args", {}).get("path")
                        if path:
                            command = path  # Store path for reference
                    
                    return AISuggestion(
                        explanation=explanation,
                        command=command,
                        tool_call=tool_call
                    )
                
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    # If JSON parsing fails, return explanation with error
                    return AISuggestion(
                        explanation=f"{explanation}\n[Error parsing tool call: {e}]"
                    )
        
        # No JSON block found - return as plain explanation
        return AISuggestion(explanation=text.strip())


class MistralBackend:
    DEFAULT_API_URL = "https://api.mistral.ai/v1/chat/completions"
    DEFAULT_MODEL = "mistral-small-latest"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.api_url = os.environ.get("MISTRAL_API_URL", self.DEFAULT_API_URL)
        self.model = model or os.environ.get("MISTRAL_MODEL", self.DEFAULT_MODEL)
        
        if not self.api_key:
            raise ValueError(
                "Mistral API key is required. Set MISTRAL_API_KEY environment variable "
                "or pass api_key to constructor."
            )
    
    def _build_system_prompt(self) -> str:
        """Construct the system prompt with tool descriptions."""
        return """You are a helpful command-line assistant for a CLI tool called sam.

Your goal is to help users accomplish tasks in their terminal by answering questions and suggesting commands.

IMPORTANT GUIDELINES:
1. Always check the conversation history first. If the question has already been answered, respond directly without running new commands.
2. Be concise and clear in your explanations.
3. Prefer simpler, more universal commands over complex ones.
4. Consider the user's OS and shell when suggesting commands.
5. If you're uncertain, explain your reasoning and ask for clarification.

AVAILABLE TOOLS:
You have access to two tools that you can call by returning a JSON object:

1. read_file - Read the contents of a file
   Format: {"tool": "read_file", "args": {"path": "<file_path>"}}
   Use this to examine file contents when the user asks about a specific file.

2. shell_command - Execute a shell command
   Format: {"tool": "shell_command", "args": {"command": "<command_string>"}}
   Use this for any general command execution (listing files, checking processes, etc.).

RESPONSE FORMAT:
- First, provide a brief explanation of what you're doing and why.
- If you need to execute a tool, include a JSON code block with the tool call.
- If you're answering from history or general knowledge, just provide the explanation.

Example with tool call:
I'll check the contents of that file for you.

```json
{"tool": "read_file", "args": {"path": "/etc/hosts"}}
```

Example without tool call:
Based on the previous output, the file contains 3 entries for localhost configuration."""
    
    def _get_system_context(self, cwd: str) -> str:
        """Get system context information."""
        os_name = platform.system()
        shell_path = os.environ.get("SHELL") or os.environ.get("COMSPEC") or "unknown"
        shell_name = os.path.basename(shell_path)
        
        return f"OS: {os_name}, Shell: {shell_name}, Current directory: {cwd}"
    
    def suggest(
        self,
        question: str,
        cwd: str,
        history: Optional[list[dict]] = None
    ) -> AISuggestion:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Build message history
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        
        if history:
            messages.extend(history)
        
        # Add current question with context
        context = self._get_system_context(cwd)
        messages.append({
            "role": "user",
            "content": f"[{context}]\n\n{question}"
        })
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1000,
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            return ResponseParser.parse(content)
        
        except requests.exceptions.Timeout:
            return AISuggestion("Request timed out. Please try again.")
        
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            if status_code == 401:
                return AISuggestion("Invalid API key. Please check your MISTRAL_API_KEY.")
            elif status_code == 429:
                return AISuggestion("Rate limit exceeded. Please wait a moment and try again.")
            else:
                return AISuggestion(f"API error ({status_code}): {e}")
        
        except requests.exceptions.RequestException as e:
            return AISuggestion(f"Network error: {e}")
        
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            return AISuggestion(f"Error parsing API response: {e}")
        
        except Exception as e:
            return AISuggestion(f"Unexpected error: {e}")


class AIBackend:
    SUPPORTED_PROVIDERS = {"mistral"}
    
    def __init__(self, provider: str = "mistral", api_key: Optional[str] = None) -> None:
        provider = provider.lower()
        
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {', '.join(self.SUPPORTED_PROVIDERS)}"
            )
        
        self.provider = provider
        
        if provider == "mistral":
            self.backend = MistralBackend(api_key=api_key)
        # Future providers can be added here
    
    def suggest(
        self,
        question: str,
        cwd: str,
        history: Optional[list[dict]] = None
    ) -> AISuggestion:
        """Get a suggestion from the AI backend."""
        return self.backend.suggest(question, cwd, history=history)