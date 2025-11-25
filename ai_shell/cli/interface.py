import os
import sys
import getpass
import platform

from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings

from ai_shell.core.session import Session
from ai_shell.core.settings import Settings
from ai_shell.cli.components.command_processor import CommandProcessor
from ai_shell.cli.components.conversation_manager import ConversationManager
from ai_shell.cli.components.output_formatter import OutputFormatter
from ai_shell.cli.components.settings_handler import SettingsHandler
from ai_shell.cli.components.path_completer import PathCompleter
from ai_shell.cli.components.command_recognizer import CommandRecognizer


class SAMInterface:
    def __init__(self):
        if 'SAM_IN_SHELL' in os.environ:
            print("You are already in a Sam shell. Use 'exit' to leave.", file=sys.stderr)
            sys.exit(1)
        os.environ['SAM_IN_SHELL'] = '1'
        
        self.console = Console()
        # Initialize Session with the user's actual current working directory
        self.session = Session(os.getcwd())
        settings_path = os.path.join(self.session.cwd, "settings.json")
        self.settings = Settings(settings_path)
        self.conversation = ConversationManager()
        self.username = getpass.getuser()
        self.hostname = platform.node()
        history_file = os.path.join(os.path.expanduser("~"), ".ai_shell_history")
        prompt_history = FileHistory(history_file)
        self.command_recognizer = CommandRecognizer()

        custom_style = Style.from_dict(
            {
                "path": "ansibrightcyan bold",
                "path_border": "ansiblue bold", # New style for the border
                "prompt": "#ffffff bold",
            }
        )

        kb = KeyBindings()

        @kb.add("c-r")
        def _(event):
            event.app.start_reverse_incremental_search()

        self.prompt_session = PromptSession(
            history=prompt_history,
            style=custom_style,
            completer=PathCompleter(self.session),
            key_bindings=kb
        )

        self.command_processor = CommandProcessor(
            self.console, self.session, self.settings, self.conversation, self.command_recognizer
        )

    def _get_prompt_text(self) -> list:
        prompt_cwd = self.session.get_display_cwd()
        return [
            ("class:path_border", "["),
            ("class:path", prompt_cwd),
            ("class:path_border", "]"),
            ("", " "), # Add a space after the bracket
            ("class:prompt", "$ "),
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
            args = text[len("/settings") :].strip()
            SettingsHandler.handle_command(self.console, self.settings, args)
            return True

        return False

    def run(self) -> None:
        self.console.clear() # Clear the console before printing the banner
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
            
            if self.command_recognizer.is_shell_command(text):
                self.command_processor.process_direct_command(text)
                self.console.print("\n")
            else:
                self.command_processor.process_ai_query(text)
                self.console.print("\n")


def run_cli() -> None:
    interface = SAMInterface()
    interface.run()
