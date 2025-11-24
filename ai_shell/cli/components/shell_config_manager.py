import os
from rich.console import Console


class ShellConfigManager:
    SUPPORTED_SHELLS = {
        "bash": ".bashrc",
        "zsh": ".zshrc",
    }

    @staticmethod
    def persist_api_key(console: Console, api_key: str) -> None:
        shell_path = os.environ.get("SHELL", "")
        shell_name = os.path.basename(shell_path) if shell_path else ""

        if shell_name not in ShellConfigManager.SUPPORTED_SHELLS:
            console.print(
                f"[yellow]Could not detect a supported shell ({', '.join(ShellConfigManager.SUPPORTED_SHELLS.keys())}). "
                "Set MISTRAL_API_KEY manually in your shell profile if desired.[/yellow]"
            )
            return

        rc_filename = ShellConfigManager.SUPPORTED_SHELLS[shell_name]
        rc_path = os.path.join(os.path.expanduser("~"), rc_filename)
        export_line = f'export MISTRAL_API_KEY="{api_key}"\n'

        try:
            if os.path.exists(rc_path):
                with open(rc_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                lines = []

            # Update or append the export line
            updated = False
            for i, line in enumerate(lines):
                if "MISTRAL_API_KEY" in line and "export" in line:
                    lines[i] = export_line
                    updated = True
                    break

            if not updated:
                if lines and not lines[-1].endswith("\n"):
                    lines.append("\n")
                lines.append(export_line)

            with open(rc_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            console.print(f"[green]✓[/green] Persisted MISTRAL_API_KEY to {rc_path}")
            console.print(f"[dim]Run: source {rc_path} to load it in current shells.[/dim]")

        except Exception as exc:
            console.print(f"[red]Failed to update shell profile: {exc}[/red]")
