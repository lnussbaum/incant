import pytest
from unittest.mock import Mock, MagicMock, patch

from incant.incant import Incant
from incant.exceptions import ConfigurationError, InstanceError, IncantError
from incant.types import InstanceConfig


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

@pytest.fixture
def mock_config_manager():
    mock = Mock()
    mock.instance_configs = {}
    return mock

@pytest.fixture
def mock_incus_cli():
    mock = Mock()
    return mock

@pytest.fixture
def mock_provision_manager():
    mock = Mock()
    return mock

@pytest.fixture
def incant_app(mock_reporter, mock_config_manager, mock_incus_cli, mock_provision_manager):
    with patch('incant.incant.ConfigManager', return_value=mock_config_manager):
        app = Incant(reporter=mock_reporter)
        app.incus = mock_incus_cli
        app.provisioner = mock_provision_manager
        return app

class TestIncant:
    def test_list_instances_success(self, incant_app, mock_config_manager, mock_reporter):
        mock_config_manager.instance_configs = {
            "instance1": InstanceConfig(name="instance1", image="img1"),
            "instance2": InstanceConfig(name="instance2", image="img2"),
        }
        incant_app.list_instances()
        assert ("echo", "instance1") in mock_reporter.messages
        assert ("echo", "instance2") in mock_reporter.messages

    def test_list_instances_no_instances(self, incant_app, mock_config_manager):
        mock_config_manager.instance_configs = {}
        with pytest.raises(ConfigurationError, match="No instances found in config."):
            incant_app.list_instances()

    def test_list_instances_no_instances_no_error(self, incant_app, mock_config_manager):
        mock_config_manager.instance_configs = {}
        incant_app.list_instances(no_error=True)
        # No exception should be raised, and no messages should be echoed
        assert not mock_config_manager.instance_configs

    def test_destroy_instance_exists(self, incant_app, mock_config_manager, mock_incus_cli, mock_reporter):
        mock_config_manager.instance_configs = {"test-instance": InstanceConfig(name="test-instance", image="img")}
        mock_incus_cli.is_instance.return_value = True
        incant_app.destroy("test-instance")
        mock_incus_cli.is_instance.assert_called_once_with("test-instance")
        mock_incus_cli.destroy_instance.assert_called_once_with("test-instance")
        assert ("success", "Destroying instance test-instance ...") in mock_reporter.messages

    def test_destroy_instance_not_exists(self, incant_app, mock_config_manager, mock_incus_cli, mock_reporter):
        mock_config_manager.instance_configs = {"test-instance": InstanceConfig(name="test-instance", image="img")}
        mock_incus_cli.is_instance.return_value = False
        incant_app.destroy("test-instance")
        mock_incus_cli.is_instance.assert_called_once_with("test-instance")
        mock_incus_cli.destroy_instance.assert_not_called()
        assert ("info", "Instance 'test-instance' does not exist.") in mock_reporter.messages

    def test_destroy_all_instances(self, incant_app, mock_config_manager, mock_incus_cli, mock_reporter):
        mock_config_manager.instance_configs = {
            "instance1": InstanceConfig(name="instance1", image="img1"),
            "instance2": InstanceConfig(name="instance2", image="img2"),
        }
        mock_incus_cli.is_instance.side_effect = [True, True]
        incant_app.destroy()
        assert mock_incus_cli.is_instance.call_count == 2
        assert mock_incus_cli.destroy_instance.call_count == 2
        assert ("success", "Destroying instance instance1 ...") in mock_reporter.messages
        assert ("success", "Destroying instance instance2 ...") in mock_reporter.messages

    def test_provision_single_instance(self, incant_app, mock_config_manager, mock_provision_manager, mock_reporter):
        instance_config = InstanceConfig(name="test-instance", image="img", provision=["step1"])
        mock_config_manager.instance_configs = {"test-instance": instance_config}
        incant_app.provision("test-instance")
        mock_provision_manager.provision.assert_called_once_with("test-instance", ["step1"])

    def test_provision_all_instances(self, incant_app, mock_config_manager, mock_provision_manager, mock_reporter):
        instance_config1 = InstanceConfig(name="instance1", image="img1", provision=["stepA"])
        instance_config2 = InstanceConfig(name="instance2", image="img2", provision=["stepB"])
        mock_config_manager.instance_configs = {
            "instance1": instance_config1,
            "instance2": instance_config2,
        }
        incant_app.provision()
        mock_provision_manager.provision.assert_any_call("instance1", ["stepA"])
        mock_provision_manager.provision.assert_any_call("instance2", ["stepB"])
        assert mock_provision_manager.provision.call_count == 2

    def test_shell_single_instance(self, incant_app, mock_config_manager, mock_incus_cli):
        mock_config_manager.instance_configs = {"single-instance": InstanceConfig(name="single-instance", image="img")}
        incant_app.shell()
        mock_incus_cli.shell.assert_called_once_with("single-instance")

    def test_shell_specific_instance(self, incant_app, mock_config_manager, mock_incus_cli):
        mock_config_manager.instance_configs = {
            "instance1": InstanceConfig(name="instance1", image="img1"),
            "instance2": InstanceConfig(name="instance2", image="img2"),
        }
        incant_app.shell("instance1")
        mock_incus_cli.shell.assert_called_once_with("instance1")

    def test_shell_multiple_instances_no_name_specified(self, incant_app, mock_config_manager):
        mock_config_manager.instance_configs = {
            "instance1": InstanceConfig(name="instance1", image="img1"),
            "instance2": InstanceConfig(name="instance2", image="img2"),
        }
        with pytest.raises(InstanceError, match="Multiple instances found. Please specify an instance name"):
            incant_app.shell()

    def test_shell_instance_not_found(self, incant_app, mock_config_manager):
        mock_config_manager.instance_configs = {"existing-instance": InstanceConfig(name="existing-instance", image="img")}
        with pytest.raises(InstanceError, match="Instance 'non-existent' not found in config"):
            incant_app.shell("non-existent")

    @patch('incant.incant.os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('builtins.print')
    def test_incant_init_success(self, mock_print, mock_open, mock_exists, incant_app):
        mock_exists.return_value = False
        incant_app.incant_init()
        mock_exists.assert_called_once_with("incant.yaml")
        mock_open.assert_called_once_with("incant.yaml", "w", encoding="utf-8")
        mock_open.return_value.__enter__.return_value.write.assert_called_once()
        mock_print.assert_called_once_with("Example configuration written to incant.yaml")

    @patch('incant.incant.os.path.exists')
    def test_incant_init_file_exists(self, mock_exists, incant_app):
        mock_exists.return_value = True
        with pytest.raises(IncantError, match="incant.yaml already exists. Aborting."):
            incant_app.incant_init()
        mock_exists.assert_called_once_with("incant.yaml")

    @patch('incant.incant.time.sleep', return_value=None)
    def test_up_single_instance_no_wait_no_provision_no_shared_folder(self, mock_sleep, incant_app, mock_config_manager, mock_incus_cli, mock_reporter):
        instance_config = InstanceConfig(name="test-instance", image="img", wait=False, provision=False, shared_folder=False)
        mock_config_manager.instance_configs = {"test-instance": instance_config}
        mock_incus_cli.is_agent_running.return_value = True
        mock_incus_cli.is_agent_usable.return_value = True

        incant_app.up("test-instance")

        mock_incus_cli.create_instance.assert_called_once_with(instance_config)
        mock_incus_cli.is_agent_running.assert_called_once_with("test-instance")
        mock_incus_cli.is_agent_usable.assert_called_once_with("test-instance")
        mock_incus_cli.is_instance_ready.assert_not_called()
        mock_incus_cli.create_shared_folder.assert_not_called()
        incant_app.provisioner.provision.assert_not_called()
        assert ("success", "Creating instance test-instance with image img...") in mock_reporter.messages
        assert ("success", "Sharing current directory to test-instance:/incant ...") in mock_reporter.messages

    @patch('incant.incant.time.sleep', return_value=None)
    def test_up_single_instance_with_wait(self, mock_sleep, incant_app, mock_config_manager, mock_incus_cli, mock_reporter):
        instance_config = InstanceConfig(name="test-instance", image="img", wait=True, provision=False, shared_folder=False)
        mock_config_manager.instance_configs = {"test-instance": instance_config}
        mock_incus_cli.is_agent_running.return_value = True
        mock_incus_cli.is_agent_usable.return_value = True
        mock_incus_cli.is_instance_ready.side_effect = [False, True] # Simulate waiting

        incant_app.up("test-instance")

        mock_incus_cli.create_instance.assert_called_once_with(instance_config)
        mock_incus_cli.is_agent_running.assert_called_once_with("test-instance")
        mock_incus_cli.is_agent_usable.assert_called_once_with("test-instance")
        mock_incus_cli.is_instance_ready.assert_called_with("test-instance", True)
        assert mock_incus_cli.is_instance_ready.call_count == 2
        assert ("info", "Waiting for test-instance to become ready...") in mock_reporter.messages
        assert ("success", "Instance test-instance is ready.") in mock_reporter.messages

    @patch('incant.incant.time.sleep', return_value=None)
    def test_up_single_instance_with_provision(self, mock_sleep, incant_app, mock_config_manager, mock_incus_cli, mock_provision_manager, mock_reporter):
        instance_config = InstanceConfig(name="test-instance", image="img", provision=["script.sh"], shared_folder=False)
        mock_config_manager.instance_configs = {"test-instance": instance_config}
        mock_incus_cli.is_agent_running.return_value = True
        mock_incus_cli.is_agent_usable.return_value = True
        mock_incus_cli.is_instance_ready.return_value = True # Provision implies wait

        incant_app.up("test-instance")

        mock_incus_cli.create_instance.assert_called_once_with(instance_config)
        mock_incus_cli.is_agent_running.assert_called_once_with("test-instance")
        mock_incus_cli.is_agent_usable.assert_called_once_with("test-instance")
        mock_incus_cli.is_instance_ready.assert_called_once_with("test-instance", True)
        incant_app.provisioner.provision.assert_called_once_with("test-instance", ["script.sh"])

    @patch('incant.incant.time.sleep', return_value=None)
    def test_up_single_instance_with_shared_folder(self, mock_sleep, incant_app, mock_config_manager, mock_incus_cli, mock_reporter):
        instance_config = InstanceConfig(name="test-instance", image="img", shared_folder=True, wait=True)
        mock_config_manager.instance_configs = {"test-instance": instance_config}
        mock_incus_cli.is_agent_running.return_value = True
        mock_incus_cli.is_agent_usable.return_value = True
        mock_incus_cli.is_instance_ready.return_value = True # Shared folder implies wait

        incant_app.up("test-instance")

        mock_incus_cli.create_instance.assert_called_once_with(instance_config)
        mock_incus_cli.is_agent_running.assert_called_once_with("test-instance")
        mock_incus_cli.is_agent_usable.assert_called_once_with("test-instance")
        mock_incus_cli.is_instance_ready.assert_called_once_with("test-instance", True)
        mock_incus_cli.create_shared_folder.assert_called_once_with("test-instance")

    @patch('incant.incant.time.sleep', return_value=None)
    def test_up_multiple_instances(self, mock_sleep, incant_app, mock_config_manager, mock_incus_cli, mock_reporter):
        instance_config1 = InstanceConfig(name="instance1", image="img1", wait=False, provision=False, shared_folder=False)
        instance_config2 = InstanceConfig(name="instance2", image="img2", wait=False, provision=False, shared_folder=False)
        mock_config_manager.instance_configs = {
            "instance1": instance_config1,
            "instance2": instance_config2,
        }
        mock_incus_cli.is_agent_running.return_value = True
        mock_incus_cli.is_agent_usable.return_value = True

        incant_app.up()

        mock_incus_cli.create_instance.assert_any_call(instance_config1)
        mock_incus_cli.create_instance.assert_any_call(instance_config2)
        assert mock_incus_cli.create_instance.call_count == 2
        assert mock_incus_cli.is_agent_running.call_count == 2
        assert mock_incus_cli.is_agent_usable.call_count == 2
        assert ("success", "Creating instance instance1 with image img1...") in mock_reporter.messages
        assert ("success", "Creating instance instance2 with image img2...") in mock_reporter.messages
        assert ("success", "Sharing current directory to instance1:/incant ...") in mock_reporter.messages
        assert ("success", "Sharing current directory to instance2:/incant ...") in mock_reporter.messages
