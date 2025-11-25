import pytest
from unittest.mock import patch
from ai_shell.execution.safe_executor import is_safe_command, run_safe_command
from ai_shell.core.session import Session
import os

@pytest.mark.parametrize(
    "command, profile, expected, reason",
    [
        ("ls -la", "standard", True, ""),
        ("echo 'hello'", "standard", True, ""),
        ("rm -rf /", "standard", False, "forbidden word"),
        ("sudo reboot", "standard", False, "forbidden word"),
        ("chgrp admin /", "strict", False, "forbidden word"),
        ("dd if=/dev/zero of=/dev/sda", "strict", False, "forbidden word"),
        ("rm -rf /", "lenient", False, "forbidden word"),
        ("cd /tmp", "standard", True, ""),
        ("cd /tmp && ls", "standard", False, "forbidden word"),
        ("", "standard", False, "Empty command"),
    ],
)
def test_is_safe_command(command, profile, expected, reason):
    safe, msg = is_safe_command(command, safety_profile=profile)
    assert safe is expected
    if not expected:
        assert reason in msg

@pytest.fixture
def session(tmp_path):
    return Session(str(tmp_path))

@patch('subprocess.Popen')
def test_run_safe_command_success(mock_popen, session):
    mock_process = mock_popen.return_value
    mock_process.stdout.readline.side_effect = ["hello\n", ""]
    mock_process.stderr.readline.return_value = ""
    mock_process.poll.return_value = 0
    mock_process.returncode = 0
    mock_process.stdout.readlines.return_value = []
    mock_process.stderr.readlines.return_value = []


    ok, retcode, stdout, stderr = run_safe_command(session, "echo 'hello'", console=None)
    assert ok is True
    assert retcode == 0
    assert stdout.strip() == "hello"
    assert stderr == ""

def test_run_safe_command_failure(session):
    ok, retcode, stdout, stderr = run_safe_command(session, "ls non_existent_dir", console=None)
    assert ok is False
    assert retcode != 0
    assert "non_existent_dir" in stderr

def test_run_safe_command_unsafe(session):
    ok, retcode, stdout, stderr = run_safe_command(session, "rm -rf /", console=None)
    assert ok is False
    assert retcode == -1
    assert "forbidden word" in stderr

def test_run_safe_command_cd(session):
    subdir = os.path.join(session.cwd, "subdir")
    os.mkdir(subdir)
    
    ok, retcode, stdout, stderr = run_safe_command(session, "cd subdir", console=None)
    assert ok is True
    assert retcode == 0
    assert session.cwd == subdir
    assert stderr == ""

def test_run_safe_command_cd_fail(session):
    ok, retcode, stdout, stderr = run_safe_command(session, "cd non_existent", console=None)
    assert ok is False
    assert retcode == -1
    assert "does not exist" in stderr

from unittest.mock import patch

@patch('subprocess.Popen')
def test_run_safe_command_interactive(mock_popen, session):
    mock_process = mock_popen.return_value
    mock_process.returncode = 0
    
    ok, retcode, stdout, stderr = run_safe_command(session, "vim my_file.txt", console=None)
    
    assert ok is True
    assert retcode == 0
    mock_popen.assert_called_once_with(
        "vim my_file.txt",
        cwd=session.cwd,
        shell=True,
        executable=os.environ.get("SHELL", "/bin/sh")
    )
    mock_process.wait.assert_called_once()

@patch('subprocess.Popen')
def test_run_safe_command_interactive_interrupt(mock_popen, session):
    mock_process = mock_popen.return_value
    mock_process.wait.side_effect = KeyboardInterrupt

    ok, retcode, stdout, stderr = run_safe_command(session, "top", console=None)

    assert ok is True
    assert retcode == 0
    assert stdout == ""
    assert stderr == ""
    mock_popen.assert_called_once()
    mock_process.wait.assert_called_once()
    mock_process.terminate.assert_called_once()

@patch('subprocess.Popen')
def test_run_safe_command_streaming_output(mock_popen, session):
    mock_process = mock_popen.return_value
    # Mock the readline to return one line at a time, then empty string
    mock_process.stdout.readline.side_effect = ["line 1\n", ""]
    mock_process.stderr.readline.side_effect = ["error 1\n", ""]
    # Mock readlines to return the rest of the lines
    mock_process.stdout.readlines.return_value = ["line 2\n", "line 3\n"]
    mock_process.stderr.readlines.return_value = ["error 2\n"]
    # Let poll return None once, then 0
    mock_process.poll.side_effect = [None, 0]
    mock_process.returncode = 0

    ok, retcode, stdout, stderr = run_safe_command(session, "my_command", console=None)

    assert ok is True
    assert stdout == "line 1\nline 2\nline 3\n"
    assert stderr == "error 1\nerror 2\n"

@patch('subprocess.Popen')
def test_run_safe_command_non_interactive_interrupt(mock_popen, session):
    mock_process = mock_popen.return_value
    mock_process.poll.side_effect = [None, KeyboardInterrupt] # Interrupt during poll
    
    ok, retcode, stdout, stderr = run_safe_command(session, "sleep 10", console=None)

    assert ok is False
    assert retcode == -1
    assert stdout == ""
    assert stderr == "Command interrupted by user."
    mock_popen.assert_called_once()
    mock_process.terminate.assert_called_once()
