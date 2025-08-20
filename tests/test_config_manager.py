import sys
from io import StringIO

import pytest
import yaml

from incant.config_manager import ConfigManager
from incant.exceptions import ConfigurationError


class MockReporter:
    def __init__(self):
        self.messages = []

    def info(self, message: str):
        self.messages.append(("info", message))

    def error(self, message: str):
        self.messages.append(("error", message))

    def success(self, message: str):
        self.messages.append(("success", message))

    def warning(self, message: str):
        self.messages.append(("warning", message))

    def header(self, message: str):
        self.messages.append(("header", message))

    def echo(self, message: str):
        self.messages.append(("echo", message))


VALID_CONFIG = {
    "instances": {
        "test-instance": {
            "image": "ubuntu/22.04",
        }
    }
}

INVALID_YAML = """
instances:
  test-instance:
    image: ubuntu/22.04
  another: [
"""
JINJA_TEMPLATE = "instances:\n  test-instance:\n    image: {{ image_name }}"
MAKO_TEMPLATE = "instances:\n  test-instance:\n    image: ${image_name}"


@pytest.fixture
def mock_reporter():
    return MockReporter()


def test_find_config_explicit_path(tmp_path, mock_reporter):
    """Test finding a config file with an explicit path."""
    config_file = tmp_path / "custom.yaml"
    config_file.write_text(yaml.dump(VALID_CONFIG))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    assert cm.find_config_file() == config_file


def test_find_config_default_names(tmp_path, monkeypatch, mock_reporter):
    """Test finding default config files in the current directory."""
    monkeypatch.chdir(tmp_path)

    # Test incant.yaml
    (tmp_path / "incant.yaml").write_text(yaml.dump(VALID_CONFIG))
    cm = ConfigManager(mock_reporter)
    assert cm.find_config_file().name == "incant.yaml"
    (tmp_path / "incant.yaml").unlink()

    # Test .incant.yaml
    (tmp_path / ".incant.yaml").write_text(yaml.dump(VALID_CONFIG))
    cm = ConfigManager(mock_reporter)
    assert cm.find_config_file().name == ".incant.yaml"


def test_find_config_no_file(tmp_path, monkeypatch, mock_reporter):
    """Test that None is returned when no config file is found."""
    monkeypatch.chdir(tmp_path)
    cm = ConfigManager(mock_reporter)
    assert cm.find_config_file() is None


def test_dump_config(tmp_path, monkeypatch, mock_reporter):
    """Test dumping the configuration to stdout."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(VALID_CONFIG))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))

    captured_output = StringIO()
    monkeypatch.setattr(sys, "stdout", captured_output)
    cm.dump_config()

    output = captured_output.getvalue()
    assert "test-instance" in output
    assert "ubuntu/22.04" in output


def test_dump_config_no_config(mock_reporter):
    """Test that dumping with no config raises an error."""
    cm = ConfigManager(mock_reporter, no_config=True)
    with pytest.raises(ConfigurationError, match="No configuration to dump"):
        cm.dump_config()
