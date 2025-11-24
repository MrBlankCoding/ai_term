import os
import shlex
import subprocess
from typing import Tuple

from ai_shell.core.session import Session


BASE_FORBIDDEN_WORDS = {"rm", "sudo", "chmod", "chown", "mv", "cp"}


def _get_forbidden_words(safety_profile: str) -> set[str]:
    profile = (safety_profile or "standard").lower()
    if profile == "lenient":
        return {"rm", "sudo"}
    if profile == "strict":
        return BASE_FORBIDDEN_WORDS.union({"chgrp", "dd"})
    return BASE_FORBIDDEN_WORDS


def is_safe_command(command: str, safety_profile: str = "standard") -> Tuple[bool, str]:
    if not command.strip():
        return False, "Empty command."
    if "\n" in command or "\r" in command:
        return False, "Multiline commands are not allowed."

    tokens = shlex.split(command)
    if not tokens:
        return False, "Unable to parse command."

    name = tokens[0]
    if name == "cd":
        if len(tokens) > 2:
            return False, "cd supports at most one argument."
        return True, ""

    # Check forbidden words
    forbidden_words = _get_forbidden_words(safety_profile)
    for t in tokens:
        lower = t.lower()
        for word in forbidden_words:
            if lower == word or lower.startswith(word + "-"):
                return False, f"Command contains forbidden word: {word}"

    return True, ""


def run_safe_command(
    session: Session, command: str, safety_profile: str = "standard"
) -> Tuple[bool, int, str, str]:
    ok, reason = is_safe_command(command, safety_profile=safety_profile)
    if not ok:
        return False, -1, "", reason

    tokens = shlex.split(command)
    if not tokens:
        return False, -1, "", "Unable to parse command."

    if tokens[0] == "cd":
        target = tokens[1] if len(tokens) == 2 else session.sandbox_root
        ok2, msg = session.change_directory(target)
        if not ok2:
            return False, -1, "", msg

        return True, 0, "", ""

    try:
        result = subprocess.run(
            command,
            cwd=session.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
            executable=os.environ.get("SHELL", "/bin/sh"),
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        return result.returncode == 0, result.returncode, stdout, stderr

    except Exception as e:
        error_message = f"Failed to execute command: {e}"
        return False, -1, "", error_message
