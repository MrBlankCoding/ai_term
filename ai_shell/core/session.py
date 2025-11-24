import os
from typing import Tuple


class Session:
    def __init__(self, sandbox_root: str) -> None:
        self.sandbox_root = os.path.abspath(sandbox_root)
        self.cwd = self.sandbox_root

    def get_display_cwd(self) -> str:
        if self.cwd == self.sandbox_root:
            return "~"
        try:
            rel = os.path.relpath(self.cwd, self.sandbox_root)
        except ValueError:
            rel = self.cwd
        return rel

    def change_directory(self, path: str) -> Tuple[bool, str]:
        if not path:
            return True, ""
        if os.path.isabs(path):
            new_path = os.path.abspath(path)
        else:
            new_path = os.path.abspath(os.path.join(self.cwd, path))
        try:
            common = os.path.commonpath([self.sandbox_root, new_path])
        except ValueError:
            return False, "Invalid path."
        if common != self.sandbox_root:
            return False, "Target directory is outside the sandbox."
        if not os.path.isdir(new_path):
            return False, "Directory does not exist."
        self.cwd = new_path
        return True, ""
