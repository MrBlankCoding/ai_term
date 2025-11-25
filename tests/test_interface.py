import pytest
from ai_shell.cli.interface import SAMInterface
from unittest.mock import MagicMock, patch
import getpass
import platform
from ai_shell.cli.components.path_completer import PathCompleter
from prompt_toolkit.document import Document
import os

@pytest.fixture
def interface():
    with patch.dict(os.environ, clear=True):
        with patch('ai_shell.cli.interface.PromptSession'):
            with patch('ai_shell.cli.interface.Settings'):
                with patch('ai_shell.cli.interface.Session') as mock_session:
                    mock_session_instance = mock_session.return_value
                    mock_session_instance.get_display_cwd.return_value = "~"
                    interface = SAMInterface()
                    interface.session = mock_session_instance
    return interface

def test_get_prompt_text(interface: SAMInterface):
    interface.session.get_display_cwd.return_value = "~/test"
    
    prompt_list = interface._get_prompt_text()
    
    assert prompt_list == [
        ("class:path_border", "["),
        ("class:path", "~/test"),
        ("class:path_border", "]"),
        ("", " "),
        ("class:prompt", "$ "),
    ]

def test_get_prompt_text_root(interface: SAMInterface):
    interface.session.get_display_cwd.return_value = "~"

    prompt_list = interface._get_prompt_text()

    assert prompt_list == [
        ("class:path_border", "["),
        ("class:path", "~"),
        ("class:path_border", "]"),
        ("", " "),
        ("class:prompt", "$ "),
    ]
@patch('os.path.isdir')
@patch('os.listdir')
def test_path_completer(mock_listdir, mock_isdir, interface: SAMInterface):
    # Mock the session's current working directory
    interface.session.cwd = "/mock/dir"
    
    # Configure mock_listdir for the initial directory
    mock_listdir.return_value = ["file1.txt", "dir_a", "file2.py", "dir_b"]
    
    # Configure mock_isdir to return True for directories and False for files
    mock_isdir.side_effect = lambda path: "dir_" in os.path.basename(path)

    completer = PathCompleter(interface.session)
    document = Document("fi", cursor_position=2)
    completions = list(completer.get_completions(document, MagicMock()))

    assert len(completions) == 2
    assert completions[0].text == "file1.txt"
    assert completions[1].text == "file2.py"

    document = Document("dir", cursor_position=3)
    completions = list(completer.get_completions(document, MagicMock()))

    assert len(completions) == 2
    assert completions[0].text == "dir_a/"
    assert completions[1].text == "dir_b/"

    # Test completing an empty string (should list all contents)
    document = Document("", cursor_position=0)
    completions = list(completer.get_completions(document, MagicMock()))
    expected_entries = ["file1.txt", "dir_a", "file2.py", "dir_b"]
    
    assert len(completions) == len(expected_entries)
    for i, entry in enumerate(expected_entries):
        assert completions[i].text == entry

@patch('sys.exit')
@patch.dict(os.environ, {'SAM_IN_SHELL': '1'})
def test_nested_shell_prevention(mock_exit):
    SAMInterface()
    mock_exit.assert_called_once_with(1)

