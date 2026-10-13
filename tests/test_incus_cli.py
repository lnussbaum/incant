from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from incant.exceptions import ConfigurationError
from incant.incus_cli import IncusCLI
from incant.reporter import Reporter
from incant.types import InstanceConfig


class TestIncusCLI:
    def test_constructor(self):
        reporter = Reporter()
        IncusCLI(reporter=reporter)

    def test_shell_handles_nonzero_exit(self):
        """
        Verify that incus shell is called with check=False to avoid raising exception on exit code.
        """
        reporter = Reporter()
        incus_cli = IncusCLI(reporter)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            # This should not raise any exception and return the exit code
            ret = incus_cli.shell("test-instance")
            assert ret == 1

            # Verify called arguments
            args, kwargs = mock_run.call_args
            assert args[0] == ["incus", "shell", "test-instance"]
            assert kwargs.get("check") is False

    def test_build_launch_command_emits_one_device_flag_per_key(self):
        """
        Each device key/value must be passed as a separate --device flag,
        matching the incus CLI's StringArrayFlag format. Combining multiple
        keys into a single comma-separated value breaks the incus parser.
        """
        config = InstanceConfig(
            name="test-instance",
            image="img",
            devices={
                "eth0": {
                    "ipv4.address": "10.115.115.100",
                    "ipv6.address": "fd42:9cbe:2600:6eaa:1266:6aff:fe1d:822",
                },
            },
        )
        command = IncusCLI(Reporter())._build_launch_command(config)

        device_flags = [command[i + 1] for i, arg in enumerate(command) if arg == "--device"]
        assert device_flags == [
            "eth0,ipv4.address=10.115.115.100",
            "eth0,ipv6.address=fd42:9cbe:2600:6eaa:1266:6aff:fe1d:822",
        ]

    def test_build_launch_command_handles_multiple_devices(self):
        config = InstanceConfig(
            name="test-instance",
            image="img",
            devices={
                "eth0": {"ipv4.address": "10.0.0.1"},
                "root": {"size": "10GiB"},
            },
        )
        command = IncusCLI(Reporter())._build_launch_command(config)

        device_flags = [command[i + 1] for i, arg in enumerate(command) if arg == "--device"]
        assert device_flags == [
            "eth0,ipv4.address=10.0.0.1",
            "root,size=10GiB",
        ]

    def test_create_shared_folders_parses_source_path(self):
        """create_shared_folders should parse '<source>:<path>' and call create_shared_folder_device."""
        incus_cli = IncusCLI(Reporter())
        with patch.object(incus_cli, "create_shared_folder_device") as mock_create:
            with patch("incant.incus_cli.Path.cwd", return_value=Path("/home/user/project")):
                incus_cli.create_shared_folders("myinst", ["./data:/data", "/abs/path:/mnt/host"])

        assert mock_create.call_count == 2
        # First call: relative source resolved against cwd
        call1 = mock_create.call_args_list[0]
        assert call1.args[0] == "myinst"  # name is positional
        assert call1.kwargs["source"] == "/home/user/project/data"
        assert call1.kwargs["path"] == "/data"
        # Second call: absolute source preserved
        call2 = mock_create.call_args_list[1]
        assert call2.args[0] == "myinst"
        assert call2.kwargs["source"] == "/abs/path"
        assert call2.kwargs["path"] == "/mnt/host"

    def test_create_shared_folders_strips_whitespace(self):
        """Whitespace around source and path should be stripped."""
        incus_cli = IncusCLI(Reporter())
        with patch.object(incus_cli, "create_shared_folder_device") as mock_create:
            with patch("incant.incus_cli.Path.cwd", return_value=Path("/home/user")):
                incus_cli.create_shared_folders("myinst", ["  ./data  :  /data  "])

        call = mock_create.call_args_list[0]
        assert call.args[0] == "myinst"
        assert call.kwargs["source"] == "/home/user/data"
        assert call.kwargs["path"] == "/data"

    def test_create_shared_folders_rejects_no_colon(self):
        """Entry without a colon should raise ConfigurationError."""
        incus_cli = IncusCLI(Reporter())
        with pytest.raises(ConfigurationError, match="expected '<source>:<path>'"):
            incus_cli.create_shared_folders("myinst", ["./data"])

    def test_create_shared_folders_rejects_too_many_colons(self):
        """Entry with multiple colons should raise ConfigurationError."""
        incus_cli = IncusCLI(Reporter())
        with pytest.raises(ConfigurationError, match="expected '<source>:<path>'"):
            incus_cli.create_shared_folders("myinst", ["./a:/foo:/bar"])

    def test_create_shared_folders_rejects_empty_source(self):
        """Entry with empty source should raise ConfigurationError."""
        incus_cli = IncusCLI(Reporter())
        with pytest.raises(ConfigurationError, match="source and path must not be empty"):
            incus_cli.create_shared_folders("myinst", [":/data"])

    def test_create_shared_folders_rejects_empty_path(self):
        """Entry with empty path should raise ConfigurationError."""
        incus_cli = IncusCLI(Reporter())
        with pytest.raises(ConfigurationError, match="source and path must not be empty"):
            incus_cli.create_shared_folders("myinst", ["./data:"])

    def test_create_shared_folder_device_name_human_readable(self):
        """Device name should include a human-readable path segment and a short hash."""
        incus_cli = IncusCLI(Reporter())
        with patch.object(incus_cli, "_run_command") as mock_run:
            with patch.object(incus_cli, "exec"):
                incus_cli.create_shared_folder_device("myinst", source="/src", path="/data")

        # Find the config device add call
        add_calls = [
            c for c in mock_run.call_args_list
            if c.args[0][:3] == ["config", "device", "add"]
        ]
        assert len(add_calls) >= 1
        device_name = add_calls[0].args[0][4]  # 5th element: instance, device_name
        assert device_name.startswith("myinst_shared_data_")

    def test_create_shared_folder_device_mount_check_uses_path(self):
        """The mount verification should grep for the actual path, not hardcoded /incant."""
        incus_cli = IncusCLI(Reporter())
        with patch.object(incus_cli, "_run_command"):
            with patch.object(incus_cli, "exec") as mock_exec:
                incus_cli.create_shared_folder_device("myinst", source="/src", path="/custom/mount")

        # Verify exec was called with the custom path in the grep command
        exec_calls = [c.args[1] for c in mock_exec.call_args_list]
        assert any("/custom/mount" in str(call) for call in exec_calls)
        # Verify /incant is NOT in any exec call
        assert not any("/incant" in str(call) for call in exec_calls)
