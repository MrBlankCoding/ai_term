import pytest
from ai_shell.ai.backend import CommandCleaner, ResponseParser, AISuggestion

@pytest.mark.parametrize(
    "input_cmd, expected_cmd",
    [
        ("  ls -la  ", "ls -la"),
        ("`ls -la`", "ls -la"),
        ('"ls -la"', "ls -la"),
        ("'ls -la'", "ls -la"),
        ("$ ls -la", "ls -la"),
        ("# ls -la", "ls -la"),
        ("> ls -la", "ls -la"),
        (">>> ls -la", "ls -la"),
        ("… ls -la", "ls -la"),
        ("echo '$VAR'", "printenv VAR"),
        ("echo $VAR", "printenv VAR"),
        ('```bash\nls -la\n```', "ls -la"),
        ('```shell\nls -la\n```', "ls -la"),
        ('```\nls -la\n```', "ls -la"),
        ("git commit -m 'feat: initial commit'", "git commit -m 'feat: initial commit'"),
        ("ls # list files", "ls"),
        ("ls #list files", "ls"),
        ("ls#list files", "ls"),
    ],
)
def test_command_cleaner(input_cmd, expected_cmd):
    assert CommandCleaner.clean(input_cmd) == expected_cmd

def test_response_parser_simple_text():
    text = "This is a simple explanation."
    suggestion = ResponseParser.parse(text)
    assert isinstance(suggestion, AISuggestion)
    assert suggestion.explanation == text
    assert suggestion.command is None
    assert suggestion.tool_call is None
    assert suggestion.metadata == {"plain_text": True}

def test_response_parser_with_shell_command():
    text = """I will list the files.

```json
{
    "tool": "shell_command",
    "args": {
        "command": "ls -la"
    }
}
```
"""
    suggestion = ResponseParser.parse(text)
    assert suggestion.explanation == "I will list the files."
    assert suggestion.command == "ls -la"
    assert suggestion.tool_call is not None
    assert suggestion.tool_call["tool"] == "shell_command"
    assert suggestion.tool_call["args"]["command"] == "ls -la"

def test_response_parser_with_read_file():
    text = """I will read the file.

```json
{
    "tool": "read_file",
    "args": {
        "path": "/path/to/file"
    }
}
```
"""
    suggestion = ResponseParser.parse(text)
    assert suggestion.explanation == "I will read the file."
    assert suggestion.command == "/path/to/file"
    assert suggestion.tool_call is not None
    assert suggestion.tool_call["tool"] == "read_file"
    assert suggestion.metadata["operation"] == "read"

def test_response_parser_with_write_file():
    text = """I will write to the file.

```json
{
    "tool": "write_file",
    "args": {
        "path": "/path/to/file",
        "content": "Hello"
    }
}
```
"""
    suggestion = ResponseParser.parse(text)
    assert suggestion.explanation == "I will write to the file."
    assert suggestion.command == "/path/to/file"
    assert suggestion.tool_call is not None
    assert suggestion.tool_call["tool"] == "write_file"
    assert suggestion.metadata["operation"] == "write"
    assert suggestion.metadata["content_length"] == 5

def test_response_parser_with_bad_json():
    text = """Here is some bad json.

```json
{
    "tool": "shell_command",
    "args": {
        "command": "ls -la"
    }
```
"""
    suggestion = ResponseParser.parse(text)
    assert "Error parsing tool JSON" in suggestion.explanation
    assert "parse_error" in suggestion.metadata
