from unittest.mock import Mock, call
import pytest
from incant.provisioners.ssh_server import SSHServer
from incant.exceptions import IncusCommandError
from incant.reporter import Reporter


@pytest.fixture
def mock_incus_cli():
    return Mock()


@pytest.fixture
def mock_reporter():
    return Mock(spec=Reporter)


def test_ssh_provisioner_misleading_error(mock_incus_cli, mock_reporter):
    # Setup
    ssh_provisioner = SSHServer(mock_incus_cli, mock_reporter)
    instance_name = "test-vm"

    # Mock behavior:
    # 1. check apt-get -> Success
    # 2. install ssh (apt-get) -> Fail (Network error)
    # 3. check dnf -> Fail (Not found)
    # 4. check pacman -> Fail (Not found)

    def side_effect(name, cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "command -v apt-get" in cmd_str:
            return ""  # Success
        if "apt-get update" in cmd_str:
            raise IncusCommandError(
                "Temporary failure resolving 'deb.debian.org'",
                stderr="Temporary failure resolving 'deb.debian.org'",
            )
        if "command -v dnf" in cmd_str:
            raise IncusCommandError("dnf not found")
        if "command -v pacman" in cmd_str:
            raise IncusCommandError("pacman not found")
        return ""

    mock_incus_cli.exec.side_effect = side_effect

    # Run
    # This should raise IncusCommandError because apt-get was found
    # but the installation failed.
    with pytest.raises(IncusCommandError) as excinfo:
        ssh_provisioner._install_ssh_server(instance_name)

    assert "Temporary failure resolving 'deb.debian.org'" in str(excinfo.value)
