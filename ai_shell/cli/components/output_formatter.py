from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.align import Align
from rich.style import Style


class OutputFormatter:
    BANNER_ASCII = r"""
 ________  ________  _____ ______      
|\   ____|\   __  \|\   _ \  _   \    
\ \  \___|\ \  |\  \ \  \\__\ \  \   
 \ \_____  \ \   __  \ \  \\|__| \  \  
  \|____|\  \ \  \ \  \ \  \    \ \  \ 
    ____\_\  \ \__\ \__\ \__\    \ \__\ 
   |\_________\|__|\|__|\|__|     \|__| 
   \|_________|
"""

    @staticmethod
    def print_banner(console: Console) -> None:
        """Print the SAM banner with improved styling."""
        lines = OutputFormatter.BANNER_ASCII.strip("\n").split("\n")

        banner_text = Text()
        for line in lines:
            banner_text.append(line + "\n", style=Style(color="green", bold=True))

        console_width = console.size.width

        console.print("=" * console_width, style="green")
        console.print(Align.center(banner_text))
        console.print("=" * console_width, style="green")
        console.print()

    @staticmethod
    def print_explanation(console: Console, explanation: str) -> None:
        markdown = Markdown(explanation.lstrip(), inline_code_theme="default")
        panel = Panel(
            markdown,
            title=Text(" Sam ", style="white on green"),
            border_style="green",
            title_align="left",
            padding=(1, 2),
        )
        console.print(panel)

    @staticmethod
    def print_output(console: Console, output: str, success: bool) -> None:
        if not output:
            return

        title = "Output" if success else "Error"
        border_style = "yellow" if success else "red"

        panel = Panel(
            output,
            title=Text(f" {title} ", style=f"white on {border_style}"),
            border_style=border_style,
            title_align="left",
            padding=(1, 2),
        )
        console.print(panel)
