import os
from pathlib import Path
from typing import Tuple


import os
from pathlib import Path
from typing import Tuple


class Session:
    def __init__(self, initial_cwd: str) -> None:
        self.cwd = os.path.abspath(initial_cwd)

    def get_display_cwd(self) -> str:
        home = str(Path.home())
        if self.cwd.startswith(home):
            return "~" + self.cwd[len(home) :]
        return self.cwd

    def change_directory(self, path: str) -> Tuple[bool, str]:
        if not path:
            path = str(Path.home())

        if path.startswith("~"):
            path = str(Path.home()) + path[1:]

        if os.path.isabs(path):
            new_path = os.path.abspath(path)
        else:
            new_path = os.path.abspath(os.path.join(self.cwd, path))

        if not os.path.isdir(new_path):
            return False, "Directory does not exist."
            
        self.cwd = new_path
        return True, ""
