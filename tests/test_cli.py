import pytest
from ai_shell.cli.components.conversation_manager import ConversationManager
from ai_shell.cli.components.file_tools import FileTools
from ai_shell.cli.components.tool_executor import ToolExecutor
from ai_shell.core.session import Session
import os

@pytest.fixture
def conversation_manager():
    return ConversationManager()

@pytest.fixture
def session(tmp_path):
    return Session(str(tmp_path))

def test_add_user_message(conversation_manager):
    conversation_manager.add_user_message("Hello")
    history = conversation_manager.get_history()
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"

def test_add_assistant_message(conversation_manager):
    conversation_manager.add_assistant_message("Hi there!")
    history = conversation_manager.get_history()
    assert len(history) == 1
    assert history[0]["role"] == "assistant"
    assert history[0]["content"] == "Hi there!"

def test_add_tool_result(conversation_manager):
    tool_call = {"tool": "shell_command", "args": {"command": "ls"}}
    conversation_manager.add_tool_result(tool_call, "file1\nfile2", True, 0.1)
    history = conversation_manager.get_history()
    assert len(history) == 1
    assert history[0]["role"] == "assistant"
    assert "[Tool Execution Result]" in history[0]["content"]
    assert "Tool: shell_command" in history[0]["content"]
    assert "Status: Success" in history[0]["content"]
    assert "Time: 0.10s" in history[0]["content"]
    assert "Output:" in history[0]["content"]
    assert "file1\nfile2" in history[0]["content"]

def test_history_trimming(conversation_manager):
    conversation_manager.MAX_HISTORY_MESSAGES = 5
    for i in range(10):
        conversation_manager.add_user_message(f"Message {i}")
    
    history = conversation_manager.get_history()
    assert len(history) == 5
    assert history[0]["content"] == "Message 5"
    assert history[4]["content"] == "Message 9"

def test_clear_history(conversation_manager):
    conversation_manager.add_user_message("test")
    conversation_manager.clear()
    assert len(conversation_manager.get_history()) == 0
    assert conversation_manager._token_estimate == 0

def test_get_summary(conversation_manager):
    conversation_manager.add_user_message("User message")
    conversation_manager.add_assistant_message("Assistant message")
    conversation_manager.add_tool_result({"tool": "shell_command", "args": {}}, "output", True)

    summary = conversation_manager.get_summary()
    assert summary["total_messages"] == 3
    assert summary["user_messages"] == 1
    assert summary["assistant_messages"] == 2
    assert summary["tool_calls"] == 1

# File Tools
def test_read_file_success(session):
    file_path = os.path.join(session.cwd, "test.txt")
    with open(file_path, "w") as f:
        f.write("hello world")

    result = FileTools.read_file(session, "test.txt")
    assert result.success is True
    assert result.output == "hello world"

def test_read_file_not_found(session):
    result = FileTools.read_file(session, "nonexistent.txt")
    assert result.success is False
    assert "not a file" in result.error

def test_read_file_is_a_directory(session):
    dir_path = os.path.join(session.cwd, "test_dir")
    os.mkdir(dir_path)
    result = FileTools.read_file(session, "test_dir")
    assert result.success is False
    assert "is not a file" in result.error

def test_write_file_success(session):
    file_path = "test_write.txt"
    content = "new content"
    
    result = FileTools.write_file(session, file_path, content)
    assert result.success is True
    
    full_path = os.path.join(session.cwd, file_path)
    assert os.path.exists(full_path)
    with open(full_path, "r") as f:
        assert f.read() == content

def test_write_file_overwrite(session):
    file_path = "overwrite.txt"
    full_path = os.path.join(session.cwd, file_path)

    with open(full_path, "w") as f:
        f.write("initial content")

    result = FileTools.write_file(session, file_path, "new content")
    assert result.success is True
    with open(full_path, "r") as f:
        assert f.read() == "new content"

# Tool Executor
def test_execute_shell_command(session):
    tool_call = {"tool": "shell_command", "args": {"command": "echo 'hello'"}}
    result = ToolExecutor.execute(session, tool_call, "standard")
    assert result.success is True
    assert result.output.strip() == "hello"

def test_execute_read_file(session):
    file_path = os.path.join(session.cwd, "read_test.txt")
    with open(file_path, "w") as f:
        f.write("read content")
    
    tool_call = {"tool": "read_file", "args": {"path": "read_test.txt"}}
    result = ToolExecutor.execute(session, tool_call, "standard")
    assert result.success is True
    assert result.output == "read content"

def test_execute_write_file(session):
    tool_call = {"tool": "write_file", "args": {"path": "write_test.txt", "content": "write content"}}
    result = ToolExecutor.execute(session, tool_call, "standard")
    assert result.success is True
    
    full_path = os.path.join(session.cwd, "write_test.txt")
    with open(full_path, "r") as f:
        assert f.read() == "write content"

def test_execute_unknown_tool(session):
    tool_call = {"tool": "unknown_tool", "args": {}}
    result = ToolExecutor.execute(session, tool_call, "standard")
    assert result.success is False
    assert "Unknown tool" in result.error

def test_execute_missing_args(session):
    tool_call = {"tool": "shell_command", "args": {}}
    result = ToolExecutor.execute(session, tool_call, "standard")
    assert result.success is False
    assert "No command provided" in result.error

    tool_call = {"tool": "read_file", "args": {}}
    result = ToolExecutor.execute(session, tool_call, "standard")
    assert result.success is False
    
    tool_call = {"tool": "write_file", "args": {}}
    result = ToolExecutor.execute(session, tool_call, "standard")
    assert result.success is False
    assert "No path provided" in result.error
