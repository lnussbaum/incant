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


@pytest.fixture
def mock_reporter():
    return MockReporter()


def run_test_with_config(tmp_path, mock_reporter, config, error_msg):
    config_file = tmp_path / "incant.yaml"
    config_file.write_text(yaml.dump(config))
    with pytest.raises(ConfigurationError, match=error_msg):
        ConfigManager(mock_reporter, config_path=str(config_file))


def test_missing_image(tmp_path, mock_reporter):
    config = {"instances": {"test": {}}}
    run_test_with_config(
        tmp_path, mock_reporter, config, "Instance 'test' is missing required 'image' field."
    )


def test_invalid_provision_type(tmp_path, mock_reporter):
    config = {"instances": {"test": {"image": "ubuntu", "provision": 123}}}
    run_test_with_config(
        tmp_path,
        mock_reporter,
        config,
        "Provisioning for instance 'test' must be a string or a list of steps.",
    )


def test_invalid_provision_step_type(tmp_path, mock_reporter):
    config = {"instances": {"test": {"image": "ubuntu", "provision": [123]}}}
    run_test_with_config(
        tmp_path,
        mock_reporter,
        config,
        "Provisioning step 0 in instance 'test' must be a string or a dictionary.",
    )


def test_provision_step_multiple_keys(tmp_path, mock_reporter):
    config = {"instances": {"test": {"image": "ubuntu", "provision": [{"copy": "a", "ssh": "b"}]}}}
    run_test_with_config(
        tmp_path,
        mock_reporter,
        config,
        "Provisioning step 0 in instance 'test' must have exactly one key",
    )


def test_provision_step_unknown_key(tmp_path, mock_reporter):
    config = {"instances": {"test": {"image": "ubuntu", "provision": [{"unknown": "a"}]}}}
    run_test_with_config(
        tmp_path,
        mock_reporter,
        config,
        "Unknown provisioning step type 'unknown' in instance 'test'",
    )


def test_copy_step_missing_fields(tmp_path, mock_reporter):
    config = {"instances": {"test": {"image": "ubuntu", "provision": [{"copy": {"source": "a"}}]}}}
    run_test_with_config(
        tmp_path,
        mock_reporter,
        config,
        "is missing required field\\(s\\): target",
    )


def test_copy_step_invalid_field_types(tmp_path, mock_reporter):
    config = {"instances": {"test": {"image": "ubuntu", "provision": [{"copy": {"source": 1, "target": 2}}]}}}
    run_test_with_config(
        tmp_path,
        mock_reporter,
        config,
        "must have string 'source' and 'target'",
    )


@pytest.mark.parametrize(
    "field,value,err",
    [
        ("uid", "a", "invalid 'uid'"),
        ("gid", "a", "invalid 'gid'"),
        ("mode", 123, "invalid 'mode'"),
        ("mode", "abc", "invalid 'mode'"),
        ("recursive", "a", "invalid 'recursive'"),
        ("create_dirs", "a", "invalid 'create_dirs'"),
    ],
)
def test_copy_step_invalid_values(tmp_path, mock_reporter, field, value, err):
    config = {
        "instances": {
            "test": {
                "image": "ubuntu",
                "provision": [{"copy": {"source": "a", "target": "b", field: value}}],
            }
        }
    }
    run_test_with_config(tmp_path, mock_reporter, config, err)


def test_invalid_ssh_step_type(tmp_path, mock_reporter):
    config = {"instances": {"test": {"image": "ubuntu", "provision": [{"ssh": 123}]}}}
    run_test_with_config(
        tmp_path,
        mock_reporter,
        config,
        "must have a boolean or dictionary value",
    )


def test_invalid_pre_launch_type(tmp_path, mock_reporter):
    config = {"instances": {"test": {"image": "ubuntu", "pre-launch": 123}}}
    run_test_with_config(
        tmp_path,
        mock_reporter,
        config,
        "Pre-launch commands for instance 'test' must be a list of strings.",
    )


def test_invalid_pre_launch_item_type(tmp_path, mock_reporter):
    config = {"instances": {"test": {"image": "ubuntu", "pre-launch": [123]}}}
    run_test_with_config(
        tmp_path,
        mock_reporter,
        config,
        "Pre-launch command 0 in instance 'test' must be a string.",
    )
