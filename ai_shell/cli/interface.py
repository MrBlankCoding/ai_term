import os
import platform

from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from ai_shell.core.session import Session
from ai_shell.core.settings import Settings
from ai_shell.cli.components.command_processor import CommandProcessor
from ai_shell.cli.components.conversation_manager import ConversationManager
from ai_shell.cli.components.output_formatter import OutputFormatter
from ai_shell.cli.components.settings_handler import SettingsHandler


class SAMInterface:
    def __init__(self):
        self.console = Console()
        self.sandbox_root = os.path.abspath(os.path.dirname(__file__))
        settings_path = os.path.join(self.sandbox_root, "settings.json")
        self.settings = Settings(settings_path)
        self.session = Session(self.sandbox_root)
        self.conversation = ConversationManager()
        self.hostname = platform.node()
        history_file = os.path.join(os.path.expanduser("~"), ".ai_shell_history")
        prompt_history = FileHistory(history_file)
        
        custom_style = Style.from_dict({
            '': '#ffffff',
            'prompt': 'ansibrightblue bold',
            'hostname': 'fg:white bg:ansiblue',
            'cursor': '#ffffff',
        })
        
        self.prompt_session = PromptSession(
            history=prompt_history,
            style=custom_style
        )
        
        self.command_processor = CommandProcessor(
            self.console,
            self.session,
            self.settings,
            self.conversation
        )
    
    def _get_prompt_text(self) -> list:
        prompt_cwd = self.session.get_display_cwd()
        return [
            ('class:hostname', f" {self.hostname} "),
            ('class:prompt', f":{prompt_cwd}> "),
        ]
    
    def _handle_builtin_command(self, text: str) -> bool:
        lower_text = text.lower()
        
        if lower_text in ("clear", "/clear"):
            self.conversation.clear()
            self.console.clear()
            self.console.print("[bold green]✓ Conversation cleared.[/bold green]")
            return True
        
        if lower_text in ("exit", "quit", "/exit", "/quit"):
            self.console.print("[bold green]Goodbye![/bold green]")
            return True
        
        if text.startswith("/settings"):
            args = text[len("/settings"):].strip()
            SettingsHandler.handle_command(self.console, self.settings, args)
            return True
        
        if text.startswith("!"):
            command = text[1:].strip()
            if command:
                self.command_processor.process_direct_command(command)
            self.console.print("\n")
            return True
        
        return False
    
    def run(self) -> None:
        OutputFormatter.print_banner(self.console)
        
        while True:
            try:
                text = self.prompt_session.prompt(self._get_prompt_text())
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[bold green]Goodbye![/bold green]")
                break
            
            if not text.strip():
                continue
            
            if self._handle_builtin_command(text):
                if text.lower() in ("exit", "quit", "/exit", "/quit"):
                    break
                continue
            
            self.command_processor.process_ai_query(text)
            self.console.print("\n")


def run_cli() -> None:
    interface = SAMInterface()
    interface.run()