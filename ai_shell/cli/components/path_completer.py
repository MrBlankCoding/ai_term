from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
import os

class PathCompleter(Completer):
    def __init__(self, session):
        self.session = session

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        
        path_to_complete = text.strip()
        base_dir = self.session.cwd

        if not path_to_complete:
            # If nothing typed yet, suggest current directory contents
            current_dir_contents = os.listdir(base_dir)
            for entry in current_dir_contents:
                yield Completion(entry, start_position=0)
            return
        
        # Get the directory part and the file/prefix part
        dirname, filename_prefix = os.path.split(path_to_complete)
        
        if dirname and not os.path.isabs(dirname) and not dirname.startswith("~"):
            # If dirname is relative, make it relative to base_dir
            search_dir = os.path.join(base_dir, dirname)
        elif dirname.startswith("~"):
            # Handle home directory expansion
            search_dir = os.path.expanduser(dirname)
        else:
            # If dirname is absolute, use it as is
            search_dir = dirname if dirname else base_dir

        try:
            for entry in os.listdir(search_dir):
                if entry.startswith(filename_prefix):
                    full_path = os.path.join(search_dir, entry)
                    if os.path.isdir(full_path):
                        yield Completion(entry + os.sep, start_position=-len(filename_prefix))
                    else:
                        yield Completion(entry, start_position=-len(filename_prefix))
        except FileNotFoundError:
            pass
        except NotADirectoryError:
            pass

