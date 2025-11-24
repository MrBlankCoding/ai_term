from typing import List
from rich.console import Console

from ai_shell.core.settings import Settings
from ai_shell.cli.components.shell_config_manager import ShellConfigManager


class SettingsHandler:
    @staticmethod
    def handle_command(console: Console, settings: Settings, args: str) -> None:
        parts = args.strip().split()

        if not parts:
            SettingsHandler._display_current_settings(console, settings)
            return

        command = parts[0].lower()

        handlers = {
            "provider": SettingsHandler._handle_provider,
            "api_key": SettingsHandler._handle_api_key,
            "safety": SettingsHandler._handle_safety,
        }

        handler = handlers.get(command)
        if handler:
            handler(console, settings, parts[1:])
        else:
            console.print(f"[red]Unknown settings option: {command}[/red]")
            SettingsHandler._display_help(console)

    @staticmethod
    def _display_current_settings(console: Console, settings: Settings) -> None:
        console.print("[bold]Current settings:[/bold]")
        console.print(f"  provider: [cyan]{settings.provider}[/cyan]")

        api_key_display = (
            "[dim]" + ("*" * min(len(settings.api_key), 20)) + "[/dim]"
            if settings.api_key
            else "[dim](not set)[/dim]"
        )
        console.print(f"  api_key: {api_key_display}")
        console.print(f"  safety_profile: [cyan]{settings.safety_profile}[/cyan]")

        SettingsHandler._display_help(console)

    @staticmethod
    def _display_help(console: Console) -> None:
        console.print("\n[bold]Commands:[/bold]")
        console.print("  [cyan]/settings provider mistral[/cyan]")
        console.print("  [cyan]/settings api_key <key>[/cyan]")
        console.print("  [cyan]/settings safety <standard|lenient|strict>[/cyan]")

    @staticmethod
    def _handle_provider(console: Console, settings: Settings, args: List[str]) -> None:
        if not args:
            console.print("[yellow]Usage: /settings provider <name>[/yellow]")
            return

        provider = args[0].lower()
        if provider != "mistral":
            console.print(f"[red]Unsupported provider: {provider}[/red]")
            return

        settings.provider = provider
        console.print(f"[green]✓[/green] Provider set to [cyan]{provider}[/cyan]")

    @staticmethod
    def _handle_api_key(console: Console, settings: Settings, args: List[str]) -> None:
        if not args:
            console.print("[yellow]Usage: /settings api_key <key>[/yellow]")
            return

        api_key = args[0]
        settings.api_key = api_key
        ShellConfigManager.persist_api_key(console, api_key)
        console.print("[green]✓[/green] API key set.")

    @staticmethod
    def _handle_safety(console: Console, settings: Settings, args: List[str]) -> None:
        if not args:
            console.print("[yellow]Usage: /settings safety <standard|lenient|strict>[/yellow]")
            return

        valid_profiles = {"standard", "lenient", "strict"}
        profile = args[0].lower()

        if profile not in valid_profiles:
            console.print(f"[red]Unsupported safety profile.[/red] " f"Use: {', '.join(valid_profiles)}")
            return

        settings.safety_profile = profile
        console.print(f"[green]✓[/green] Safety profile set to [cyan]{profile}[/cyan]")
