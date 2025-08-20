import sys
from io import StringIO

import pytest
import yaml
from jinja2 import exceptions as jinja_exceptions
from mako import exceptions as mako_exceptions

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
    """Test that ConfigurationError is raised when no config file is found."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigurationError, match="Config file not found"):
        ConfigManager(mock_reporter)


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


def test_load_config_file_not_found(tmp_path, mock_reporter):
    """Test loading a non-existent config file raises ConfigurationError."""
    config_file = tmp_path / "non_existent.yaml"
    cm = ConfigManager(mock_reporter, config_path=str(config_file), no_config=True)
    with pytest.raises(ConfigurationError, match="Config file not found"):
        cm.load_config()


def test_load_config_jinja_template_error(tmp_path, mock_reporter):
    """Test that Jinja2 template rendering errors are caught."""
    config_file = tmp_path / "incant.yaml.j2"
    config_file.write_text("{{ invalid_syntax ")
    cm = ConfigManager(mock_reporter, config_path=str(config_file), no_config=True)
    with pytest.raises(ConfigurationError, match="Error rendering template") as excinfo:
        cm.load_config()
    assert isinstance(excinfo.value.__cause__, jinja_exceptions.TemplateSyntaxError)


def test_load_config_mako_template_error(tmp_path, mock_reporter):
    """Test that Mako template rendering errors are caught."""
    config_file = tmp_path / "incant.yaml.mako"
    config_file.write_text("${ invalid_syntax ")
    cm = ConfigManager(mock_reporter, config_path=str(config_file), no_config=True)
    with pytest.raises(ConfigurationError, match="Error rendering template") as excinfo:
        cm.load_config()
    assert isinstance(excinfo.value.__cause__, mako_exceptions.SyntaxException)


def test_load_config_yaml_error(tmp_path, mock_reporter):
    """Test that YAML parsing errors are caught."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(INVALID_YAML)
    cm = ConfigManager(mock_reporter, config_path=str(config_file), no_config=True)
    with pytest.raises(ConfigurationError, match="Error parsing YAML file") as excinfo:
        cm.load_config()
    assert isinstance(excinfo.value.__cause__, yaml.YAMLError)


def test_dump_config_exception(tmp_path, monkeypatch, mock_reporter):
    """Test that exceptions during config dumping are caught."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(VALID_CONFIG))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))

    def mock_dump(*args, **kwargs):
        raise Exception("Mock dump error")

    monkeypatch.setattr(yaml, "dump", mock_dump)
    with pytest.raises(ConfigurationError, match="Error dumping configuration: Mock dump error"):
        cm.dump_config()


def test_find_config_verbose_output(tmp_path, mock_reporter):
    """Test verbose output when config file is found."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(VALID_CONFIG))
    cm = ConfigManager(mock_reporter, config_path=str(config_file), verbose=True)
    cm.find_config_file()
    assert any("Config found at:" in msg for _, msg in mock_reporter.messages)

def test_load_config_verbose_output(tmp_path, mock_reporter):
    """Test verbose output when config is loaded successfully."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(VALID_CONFIG))
    cm = ConfigManager(mock_reporter, config_path=str(config_file), verbose=True)
    cm.load_config()
    assert any("Config loaded successfully from" in msg for _, msg in mock_reporter.messages)

def test_validate_config_no_instances(tmp_path, mock_reporter):
    """Test that validate_config raises ConfigurationError if no instances are found."""
    config = {"instances": {}}
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    with pytest.raises(ConfigurationError, match="No instances found in config"):
        ConfigManager(mock_reporter, config_path=str(config_file))

def test_init_with_empty_config_file(tmp_path, mock_reporter):
    """Test that ConfigManager handles an empty config file gracefully."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text("") # Empty file
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    assert cm._config_data is None
    assert cm.instance_configs == {}

def test_init_with_no_instances_in_config(tmp_path, mock_reporter):
    """Test that ConfigManager handles a config file with no instances section."""
    config = {"some_other_section": {}}
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    with pytest.raises(ConfigurationError, match="No instances found in config"):
        ConfigManager(mock_reporter, config_path=str(config_file))

def test_valid_config_no_provision(tmp_path, mock_reporter):
    """Test a valid config without a 'provision' section."""
    config = {"instances": {"test": {"image": "ubuntu"}}}
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    # No exception should be raised
    assert cm.instance_configs["test"].provision is None

def test_valid_config_no_pre_launch(tmp_path, mock_reporter):
    """Test a valid config without a 'pre-launch' section."""
    config = {"instances": {"test": {"image": "ubuntu"}}}
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    # No exception should be raised
    assert cm.instance_configs["test"].pre_launch_cmds == []
