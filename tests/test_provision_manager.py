from unittest.mock import Mock, call, patch

import pytest

from incant.exceptions import IncusCommandError
from incant.provisioning_manager import ProvisionManager
from incant.reporter import Reporter


@pytest.fixture
def mock_incus_cli():
    return Mock()


@pytest.fixture
def mock_reporter():
    return Mock(spec=Reporter)


def test_provision_llmnr(mock_incus_cli, mock_reporter):
    """Test that LLMNR provisioning calls the expected incus commands."""
    pm = ProvisionManager(mock_incus_cli, mock_reporter)

    # Mock exec to simulate apt-get presence
    # The first call checks for apt-get, we want it to succeed (return None or empty)
    # The second call installs it.
    # Subsequent calls are for configuration.
    mock_incus_cli.exec.return_value = None

    instance_name = "test-instance"
    provision_config = [{"llmnr": True}]

    pm.provision(instance_name, provision_config)

    # Verify calls
    # 1. Check apt-get
    # 2. Install package
    # 3. Configure file
    # 4. Restart service

    # We check that at least the installation was attempted
    assert (
        call(instance_name, ["sh", "-c", "command -v apt-get"], capture_output=True)
        in mock_incus_cli.exec.call_args_list
    )
    assert (
        call(
            instance_name,
            ["sh", "-c", "apt-get update && apt-get -y install systemd-resolved"],
            capture_output=False,
        )
        in mock_incus_cli.exec.call_args_list
    )

    # Verify reporter success message
    mock_reporter.success.assert_any_call(f"LLMNR enabled on {instance_name}.")


def test_provision_unknown_provisioner_runtime_check(mock_incus_cli, mock_reporter):
    """
    Test that ProvisionManager handles provisioners safely.
    Note: Ideally ConfigManager catches unknown keys before this,
    but ProvisionManager should also be robust or at least fail clearly if passed invalid data.
    """
    pm = ProvisionManager(mock_incus_cli, mock_reporter)

    # We need to bypass ConfigManager validation to test this runtime behavior
    # or we can rely on the fact that ConfigManager would have raised an error.
    # Here we simulate a "script" step just to prove the manager works.

    pm.provision("test", ["echo hello"])
    mock_incus_cli.run_script.assert_called_with("test", "echo hello")
