import os
import shlex
import subprocess
from typing import Tuple
import sys
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from ai_shell.cli.components.command_recognizer import CommandRecognizer
from ai_shell.core.session import Session


BASE_FORBIDDEN_WORDS = {"rm", "sudo", "&&", "||", ";", "|", "`", "$(", "<", ">"}


def _get_forbidden_words(safety_profile: str) -> set[str]:
    profile = (safety_profile or "standard").lower()
    if profile == "lenient":
        return {"rm", "sudo", "&&", "||", ";", "|", "`", "$(", "<", ">"}
    if profile == "strict":
        return BASE_FORBIDDEN_WORDS.union({"chgrp", "dd"})
    return BASE_FORBIDDEN_WORDS


def is_safe_command(command: str, safety_profile: str = "standard") -> Tuple[bool, str]:
    if not command.strip():
        return False, "Empty command."

    try:
        tokens = shlex.split(command)
    except ValueError as e:
        return False, f"Unable to parse command: {e}"

    if not tokens:
        return False, "Unable to parse command."

    # Check forbidden words first
    forbidden_words = _get_forbidden_words(safety_profile)
    for t in tokens:
        lower = t.lower()
        for word in forbidden_words:
            if lower == word or lower.startswith(word + "-"):
                return False, f"Command contains forbidden word: {word}"

    name = tokens[0]
    if name == "cd":
        if len(tokens) > 2:
            return False, "cd supports at most one argument."
        return True, ""

    return True, ""


def run_safe_command(
    session: Session, command: str, safety_profile: str = "standard", recognizer: 'CommandRecognizer' = None, console: Console = None
) -> Tuple[bool, int, str, str]:
    ok, reason = is_safe_command(command, safety_profile=safety_profile)
    if not ok:
        return False, -1, "", reason

    tokens = shlex.split(command)
    if not tokens:
        return False, -1, "", "Unable to parse command."

    if tokens[0] == "cd":
        target = tokens[1] if len(tokens) == 2 else os.path.expanduser("~")
        ok2, msg = session.change_directory(target)
        if not ok2:
            return False, -1, "", msg

        return True, 0, "", ""

    try:
        # Defer the import to avoid circular dependency
        from ai_shell.cli.components.command_recognizer import CommandRecognizer
        if recognizer is None:
            recognizer = CommandRecognizer()

        if recognizer.is_interactive(command):
            # For interactive commands, run in a non-blocking way and let it take over the TTY
            try:
                process = subprocess.Popen(
                    command,
                    cwd=session.cwd,
                    shell=True,
                    executable=os.environ.get("SHELL", "/bin/sh")
                )
                process.wait()  # Wait for the command to complete
                return True, process.returncode, "", ""
            except KeyboardInterrupt:
                process.terminate()
                # The user pressed Ctrl+C to exit the interactive command.
                # This is expected behavior, so we'll return success.
                return True, 0, "", ""
        else:
            # For non-interactive commands, stream the output
            try:
                process = subprocess.Popen(
                    command,
                    cwd=session.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=True,
                    executable=os.environ.get("SHELL", "/bin/sh"),
                    bufsize=1,  # Line-buffered
                    universal_newlines=True
                )
                
                output_lines = []
                stdout_str_list = []
                stderr_str_list = []
                MAX_LINES = 50

                if console:
                    with Live(console=console, auto_refresh=False) as live:
                        while process.poll() is None:
                            if process.stdout:
                                output = process.stdout.readline()
                                if output:
                                    output_lines.append(Text(output, style="green"))
                                    stdout_str_list.append(output)
                                    
                            if process.stderr:
                                error_output = process.stderr.readline()
                                if error_output:
                                    output_lines.append(Text(error_output, style="red"))
                                    stderr_str_list.append(error_output)
                            
                            if len(output_lines) > MAX_LINES:
                                output_lines = output_lines[-MAX_LINES:]
                                
                            live.update(Panel(Text("\n").join(output_lines), title="Output", border_style="blue"), refresh=True)
                else:
                    # Fallback for when console is not provided (e.g. in tests)
                    while process.poll() is None:
                        if process.stdout:
                            output = process.stdout.readline()
                            if output:
                                stdout_str_list.append(output)
                        
                        if process.stderr:
                            error_output = process.stderr.readline()
                            if error_output:
                                stderr_str_list.append(error_output)

                returncode = process.wait()
                
                full_stdout = "".join(stdout_str_list)
                full_stderr = "".join(stderr_str_list)

                return returncode == 0, returncode, full_stdout, full_stderr

            except KeyboardInterrupt:
                if process:
                    process.terminate()
                return False, -1, "", "Command interrupted by user."

    except Exception as e:
        error_message = f"Failed to execute command: {e}"
        return False, -1, "", error_message
