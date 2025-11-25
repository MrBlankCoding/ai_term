from rich.panel import Panel
from rich.text import Text


class ThinkingLog:
    def __init__(self):
        self.logs = []
        self.title = "[bold cyan]Thinking...[/bold cyan]"

    def add(self, message: str):
        self.logs.append(message)

    def update_last(self, message: str):
        if self.logs:
            self.logs[-1] = message

    def complete(self, message: str = "Done"):
        self.title = f"[bold green]{message}[/bold green]"

    def __rich_console__(self, console, options):
        log_text = Text("\n".join(self.logs))
        yield Panel(log_text, title=self.title, border_style="cyan")
