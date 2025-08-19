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


def test_load_config_simple_yaml(tmp_path, mock_reporter):
    """Test loading a simple YAML file."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(VALID_CONFIG))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    assert cm.config_data == VALID_CONFIG


def test_load_config_jinja_template(tmp_path, mock_reporter):
    """Test loading and rendering a Jinja2 template."""
    config_file = tmp_path / "incant.yaml.j2"
    config_file.write_text(JINJA_TEMPLATE.replace("{{ image_name }}", "ubuntu/22.04"))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    assert cm.config_data["instances"]["test-instance"]["image"] == "ubuntu/22.04"


def test_load_config_mako_template(tmp_path, mock_reporter):
    """Test loading and rendering a Mako template."""
    config_file = tmp_path / "incant.yaml.mako"
    config_file.write_text(MAKO_TEMPLATE.replace("${image_name}", "debian/11"))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    assert cm.config_data["instances"]["test-instance"]["image"] == "debian/11"


def test_load_config_invalid_yaml(tmp_path, mock_reporter):
    """Test that a YAMLError is raised for invalid YAML."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(INVALID_YAML)
    with pytest.raises(ConfigurationError, match="Error parsing YAML file"):
        ConfigManager(mock_reporter, config_path=str(config_file))


def test_validate_config_valid(tmp_path, mock_reporter):
    """Test that a valid config passes validation."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(VALID_CONFIG))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    cm.validate_config()  # Should not raise


def test_validate_config_no_instances(tmp_path, mock_reporter):
    """Test that a config without 'instances' fails validation."""
    config_file = tmp_path / "incant.yaml"
    config_file.write_text("other: data")
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    with pytest.raises(ConfigurationError, match="No instances found in config"):
        cm.validate_config()


def test_validate_config_missing_image(tmp_path, mock_reporter):
    """Test that an instance missing 'image' fails validation."""
    config = {"instances": {"test-instance": {"vm": True}}}
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    with pytest.raises(ConfigurationError, match="is missing required 'image' field"):
        cm.validate_config()


def test_validate_config_unknown_field(tmp_path, mock_reporter):
    """Test that an instance with an unknown field fails validation."""
    config = {"instances": {"test-instance": {"image": "ubuntu", "unknown": "field"}}}
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    with pytest.raises(ConfigurationError, match="Unknown field 'unknown'"):
        cm.validate_config()


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


def test_validate_provision_valid_string(tmp_path, mock_reporter):
    """Test that a valid provision string passes validation."""
    config = {
        "instances": {
            "test-instance": {
                "image": "ubuntu/22.04",
                "provision": "path/to/script.sh",
            }
        }
    }
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    cm.validate_config()


def test_validate_provision_valid_list(tmp_path, mock_reporter):
    """Test that a valid provision list passes validation."""
    config = {
        "instances": {
            "test-instance": {
                "image": "ubuntu/22.04",
                "provision": [
                    "path/to/script.sh",
                    {"copy": {"src": "a", "dest": "b"}},
                    {"ssh": True},
                ],
            }
        }
    }
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    cm.validate_config()


def test_validate_provision_invalid_type(tmp_path, mock_reporter):
    """Test that a provision field with an invalid type fails validation."""
    config = {"instances": {"test-instance": {"image": "ubuntu/22.04", "provision": 123}}}
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    with pytest.raises(ConfigurationError, match="must be a string or a list of steps"):
        cm.validate_config()


def test_validate_provision_invalid_step_multiple_keys(tmp_path, mock_reporter):
    """Test that a provision step with multiple keys fails validation."""
    config = {
        "instances": {
            "test-instance": {
                "image": "ubuntu/22.04",
                "provision": [{"copy": {"src": "a", "dest": "b"}, "ssh": True}],
            }
        }
    }
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    with pytest.raises(ConfigurationError, match="must have exactly one key"):
        cm.validate_config()


def test_validate_provision_invalid_step_unknown_type(tmp_path, mock_reporter):
    """Test that a provision step with an unknown type fails validation."""
    config = {
        "instances": {
            "test-instance": {
                "image": "ubuntu/22.04",
                "provision": [{"unknown": "step"}],
            }
        }
    }
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    with pytest.raises(ConfigurationError, match="Unknown provisioning step type"):
        cm.validate_config()


def test_validate_provision_invalid_copy_value(tmp_path, mock_reporter):
    """Test that a 'copy' provision step with a non-dictionary value fails."""
    config = {
        "instances": {"test-instance": {"image": "ubuntu/22.04", "provision": [{"copy": "value"}]}}
    }
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    with pytest.raises(ConfigurationError, match="must have a dictionary value"):
        cm.validate_config()


def test_validate_provision_invalid_ssh_value(tmp_path, mock_reporter):
    """Test that an 'ssh' provision step with an invalid value fails."""
    config = {
        "instances": {"test-instance": {"image": "ubuntu/22.04", "provision": [{"ssh": "string"}]}}
    }
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    cm = ConfigManager(mock_reporter, config_path=str(config_file))
    with pytest.raises(ConfigurationError, match="must have a boolean or dictionary value"):
        cm.validate_config()
