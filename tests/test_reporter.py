from unittest.mock import patch

from incant.reporter import Reporter


class TestReporter:
    def test_print_etc_hosts_lines_global_addresses(self):
        """Only global-scope addresses on non-lo interfaces are printed."""
        reporter = Reporter()
        network = {
            "lo": {"addresses": [{"address": "127.0.0.1", "scope": "global"}]},
            "eth0": {
                "addresses": [
                    {"address": "10.0.0.5", "scope": "global"},
                    {"address": "fe80::1", "scope": "link"},
                    {"address": "fd42::1", "scope": "global"},
                ]
            },
        }

        with patch("click.echo") as mock_echo:
            reporter.print_etc_hosts_lines("myhost", network)

        calls = [c.args[0] for c in mock_echo.call_args_list]
        # lo is skipped, link-local is skipped
        assert len(calls) == 2
        assert any("10.0.0.5" in c and "myhost" in c and "eth0" in c for c in calls)
        assert any("fd42::1" in c and "myhost" in c and "eth0" in c for c in calls)

    def test_print_etc_hosts_lines_empty_network(self):
        """No addresses -> no output."""
        reporter = Reporter()
        with patch("click.echo") as mock_echo:
            reporter.print_etc_hosts_lines("myhost", {})
        mock_echo.assert_not_called()

    def test_print_etc_hosts_lines_missing_addresses_key(self):
        """Interface without 'addresses' key is handled gracefully."""
        reporter = Reporter()
        network = {"eth0": {}}
        with patch("click.echo") as mock_echo:
            reporter.print_etc_hosts_lines("myhost", network)
        mock_echo.assert_not_called()
