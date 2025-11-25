import shutil
import os

class CommandRecognizer:
    def __init__(self):
        # A set of common shell built-in commands
        self.built_in_commands = {
            "cd", "echo", "export", "alias", "unalias", "exit", "quit", 
            "history", "source", "jobs", "fg", "bg", "kill", "type"
        }
        # A set of words that usually start a natural language query
        self.question_words = {
            "what", "who", "when", "where", "why", "how", "which", "is",
            "list", "show", "find", "get", "can", "do", "does"
        }
        self.interactive_commands = {
            "top", "htop", "vim", "vi", "nano", "pico", "less", "more", "man", "ssh"
        }

    def is_shell_command(self, text: str) -> bool:
        if not text.strip():
            return False

        command_parts = text.strip().split()
        command = command_parts[0].lower()

        if command in self.question_words:
            return False

        if command in self.built_in_commands:
            return True

        if shutil.which(command):
            return True
            
        if os.path.isfile(command) and os.access(command, os.X_OK):
            return True

        return False
    
    def is_interactive(self, text: str) -> bool:
        if not text.strip():
            return False
        
        command = text.strip().split()[0].lower()
        return command in self.interactive_commands
