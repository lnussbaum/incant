from unittest.mock import patch
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
