import subprocess
from unittest.mock import patch
from incant.incus_cli import IncusCLI
from incant.reporter import Reporter


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
