import pytest
from ai_shell.cli.components.command_recognizer import CommandRecognizer
from unittest.mock import patch
import os

@pytest.fixture
def recognizer():
    return CommandRecognizer()

def test_is_shell_command_built_in(recognizer: CommandRecognizer):
    assert recognizer.is_shell_command("cd /tmp")
    assert recognizer.is_shell_command("echo 'hello'")
    assert recognizer.is_shell_command("exit")

@patch('shutil.which')
def test_is_shell_command_in_path(mock_which, recognizer: CommandRecognizer):
    mock_which.return_value = "/bin/ls"
    assert recognizer.is_shell_command("ls -l")
    mock_which.assert_called_with("ls")

@patch('shutil.which')
def test_is_shell_command_not_a_command(mock_which, recognizer: CommandRecognizer):
    mock_which.return_value = None
    assert not recognizer.is_shell_command("thisisnotacommand")
    mock_which.assert_called_with("thisisnotacommand")

@patch('os.path.isfile')
@patch('os.access')
def test_is_shell_command_executable_file(mock_access, mock_isfile, recognizer: CommandRecognizer):
    mock_isfile.return_value = True
    mock_access.return_value = True
    assert recognizer.is_shell_command("./my_script.sh")
    mock_isfile.assert_called_with("./my_script.sh")
    mock_access.assert_called_with("./my_script.sh", os.X_OK)

def test_is_shell_command_natural_language(recognizer: CommandRecognizer):
    assert not recognizer.is_shell_command("list all the files in the current directory")
    assert not recognizer.is_shell_command("what is the current date?")

def test_is_interactive(recognizer: CommandRecognizer):
    assert recognizer.is_interactive("top")
    assert recognizer.is_interactive("vim my_file.txt")
    assert not recognizer.is_interactive("ls -l")
    assert not recognizer.is_interactive("echo 'hello'")
