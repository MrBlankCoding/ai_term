import pytest
import os
from ai_shell.core.session import Session

@pytest.fixture
def session(tmp_path):
    return Session(str(tmp_path))

def test_session_initialization(session, tmp_path):
    assert session.cwd == str(tmp_path)
    assert os.path.isdir(session.cwd)

def test_get_display_cwd(session, tmp_path):
    assert session.get_display_cwd() == str(tmp_path)

    sub_dir = os.path.join(session.cwd, "test_dir")
    os.mkdir(sub_dir)
    session.change_directory("test_dir")

    assert session.get_display_cwd() == os.path.join(str(tmp_path), "test_dir")

def test_get_display_cwd_home_directory(session):
    home = os.path.expanduser("~")
    session.cwd = home
    assert session.get_display_cwd() == "~"

    test_dir = os.path.join(home, "test_dir")
    session.cwd = test_dir
    assert session.get_display_cwd() == "~/test_dir"

def test_change_directory_success(session):
    sub_dir_name = "a"
    sub_dir = os.path.join(session.cwd, sub_dir_name)
    os.mkdir(sub_dir)

    ok, msg = session.change_directory(sub_dir_name)
    assert ok is True
    assert msg == ""
    assert session.cwd == sub_dir

    ok, msg = session.change_directory("..")
    assert ok is True
    assert msg == ""
    assert session.cwd == os.path.dirname(sub_dir)

def test_change_directory_to_root_with_empty_path(session):
    sub_dir_name = "subdir"
    sub_dir = os.path.join(session.cwd, sub_dir_name)
    os.mkdir(sub_dir)
    session.change_directory(sub_dir_name)
    
    ok, msg = session.change_directory("")
    assert ok is True
    assert session.cwd == os.path.expanduser("~")

def test_change_directory_nonexistent(session):
    ok, msg = session.change_directory("nonexistent_dir")
    assert ok is False
    assert "does not exist" in msg