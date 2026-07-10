import os
import sys
from unittest.mock import mock_open, patch
import pytest
import src.config


def test_load_env_no_file():
    # If .env does not exist, load_env should return early and not crash or modify os.environ
    with patch("src.config.os.path.exists", return_value=False):
        # We ensure a clean env check
        original_env_count = len(os.environ)
        src.config.load_env()
        assert len(os.environ) == original_env_count


def test_load_env_with_content():
    env_content = """
# This is a comment line that should be skipped
PORT=9999
HOST=127.0.0.1 # inline comment to be stripped
INVALID_LINE_NO_EQUALS
ANOTHER_KEY="value"
SPACEY_KEY =  spacey_value 
EMPTY_KEY=
    """
    with patch("src.config.os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=env_content)), \
         patch.dict("os.environ", {}, clear=True):
        src.config.load_env()
        assert os.environ.get("PORT") == "9999"
        assert os.environ.get("HOST") == "127.0.0.1"
        assert os.environ.get("ANOTHER_KEY") == "value"
        assert os.environ.get("SPACEY_KEY") == "spacey_value"
        assert os.environ.get("EMPTY_KEY") == ""
        assert "INVALID_LINE_NO_EQUALS" not in os.environ


def test_load_env_bundled_exe():
    # Test path resolution when hasattr(sys, '_MEIPASS') is true
    env_content = "BUNDLED_MODE=true"
    with patch("src.config.os.path.exists", return_value=True) as mock_exists, \
         patch("builtins.open", mock_open(read_data=env_content)), \
         patch.dict("os.environ", {}, clear=True), \
         patch.object(sys, "_MEIPASS", "mocked_meipass", create=True), \
         patch.object(sys, "executable", "C:\\mocked\\ReclipControl.exe", create=True):
        src.config.load_env()
        # Verify that os.path.exists was called with the path next to the executable
        mock_exists.assert_called_with("C:\\mocked\\.env")
        assert os.environ.get("BUNDLED_MODE") == "true"
