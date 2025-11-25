from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.align import Align
from rich.style import Style
from rich.progress import Progress, SpinnerColumn, TextColumn
from contextlib import contextmanager
from typing import Optional


class OutputFormatter:
    """Enhanced output formatter with better visual feedback and consistency."""

    BANNER_ASCII = r"""
    
 ________  ________  _____ ______      
|\   ____\|\   __  \|\   _ \  _   \    
\ \  \___|\ \  \|\  \ \  \\\__\ \  \   
 \ \_____  \ \   __  \ \  \\|__| \  \  
  \|____|\  \ \  \ \  \ \  \    \ \  \ 
    ____\_\  \ \__\ \__\ \__\    \ \__\
   |\_________\|__|\|__|\|__|     \|__|
   \|_________|                        
                                          

"""

    COLORS = {
        "primary": "green",
        "secondary": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "info": "cyan",
        "tool": "magenta",
    }

    @staticmethod
    def print_banner(console: Console, version: str = "1.0.0") -> None:
        lines = OutputFormatter.BANNER_ASCII.strip("\n").split("\n")

        banner_text = Text()
        for line in lines:
            banner_text.append(line + "\n", style=Style(color="green", bold=True))

        console_width = console.size.width

        console.print("=" * console_width, style="green")
        console.print(Align.center(banner_text))
        console.print(
            Align.center(f"[dim]Shell AI Manager v{version}[/dim]"), style="green"
        )
        console.print("=" * console_width, style="green")
        console.print()

    @staticmethod
    def print_explanation(
        console: Console, explanation: str, title: str = "Sam"
    ) -> None:
        if not explanation.strip():
            return

        markdown = Markdown(explanation.lstrip(), inline_code_theme="monokai")
        console_width = console.size.width

        panel = Panel(
            markdown,
            title=Text(f" {title} ", style="white on green"),
            border_style="green",
            title_align="left",
            padding=(1, 2),
            width=console_width,
        )
        console.print(panel)

    @staticmethod
    def print_output(
        console: Console,
        output: str,
        success: bool,
        execution_time: Optional[float] = None,
    ) -> None:
        if not output:
            return

        title_parts = ["Output" if success else "Error"]
        if execution_time is not None:
            title_parts.append(f"({execution_time:.2f}s)")
        title = " ".join(title_parts)

        border_style = "yellow" if success else "red"
        console_width = console.size.width

        panel = Panel(
            output.rstrip(),
            title=Text(f" {title} ", style=f"white on {border_style}"),
            border_style=border_style,
            title_align="left",
            padding=(1, 2),
            width=console_width,
        )
        console.print(panel)

    @staticmethod
    def print_command(console: Console, command: str, tool: str = "shell") -> None:
        console_width = console.size.width

        # Add icon based on tool type
        icons = {"shell": "►", "read": "◄", "write": "◊"}
        icon = icons.get(tool, "•")

        panel = Panel(
            f"[bold cyan]{icon} {command}[/bold cyan]",
            title=Text(" Command ", style="white on blue"),
            border_style="blue",
            title_align="left",
            padding=(1, 2),
            width=console_width,
        )
        console.print(panel)

    @staticmethod
    def print_reading_file(console: Console, path: str) -> None:
        console_width = console.size.width
        panel = Panel(
            f"[cyan]◄ {path}[/cyan]",
            title=Text(" Reading file ", style="white on magenta"),
            border_style="magenta",
            title_align="left",
            padding=(1, 2),
            width=console_width,
        )
        console.print(panel)

    @staticmethod
    def print_writing_file(
        console: Console, path: str, size: Optional[int] = None
    ) -> None:
        console_width = console.size.width

        content = f"[cyan]◊ {path}[/cyan]"
        if size is not None:
            content += f"\n[dim]{size} bytes[/dim]"

        panel = Panel(
            content,
            title=Text(" Writing file ", style="white on purple"),
            border_style="purple",
            title_align="left",
            padding=(1, 2),
            width=console_width,
        )
        console.print(panel)

    @staticmethod
    def print_error(
        console: Console, message: str, exception: Optional[Exception] = None
    ) -> None:
        console_width = console.size.width

        content = f"[bold red]✗ {message}[/bold red]"
        if exception:
            content += f"\n[dim]{type(exception).__name__}: {str(exception)}[/dim]"

        panel = Panel(
            content,
            title=Text(" Error ", style="white on red"),
            border_style="red",
            title_align="left",
            padding=(1, 2),
            width=console_width,
        )
        console.print(panel)

    @staticmethod
    def print_warning(console: Console, message: str) -> None:
        console_width = console.size.width

        panel = Panel(
            f"[bold yellow]▲ {message}[/bold yellow]",
            title=Text(" Warning ", style="black on yellow"),
            border_style="yellow",
            title_align="left",
            padding=(1, 2),
            width=console_width,
        )
        console.print(panel)

    @staticmethod
    def print_info(console: Console, message: str) -> None:
        console_width = console.size.width

        panel = Panel(
            f"[cyan]ℹ {message}[/cyan]",
            title=Text(" Info ", style="white on cyan"),
            border_style="cyan",
            title_align="left",
            padding=(1, 2),
            width=console_width,
        )
        console.print(panel)

    @staticmethod
    @contextmanager
    def spinner(console: Console, message: str = "Processing..."):
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(description=message, total=None)
            yield progress

    @staticmethod
    def print_divider(console: Console, char: str = "─") -> None:
        console.print(char * console.size.width, style="dim")
