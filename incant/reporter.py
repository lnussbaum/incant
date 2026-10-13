import click

from .constants import CLICK_STYLE


class Reporter:
    def info(self, message: str) -> None:
        click.secho(message, **CLICK_STYLE["info"])

    def error(self, message: str) -> None:
        click.secho(message, **CLICK_STYLE["error"])

    def success(self, message: str) -> None:
        click.secho(message, **CLICK_STYLE["success"])

    def warning(self, message: str) -> None:
        click.secho(message, **CLICK_STYLE["warning"])

    def header(self, message: str) -> None:
        click.secho(message, **CLICK_STYLE["header"])

    def echo(self, message: str) -> None:
        click.echo(message)

    def print_etc_hosts_lines(self, host: str, network: dict) -> None:
        """Print /etc/hosts lines for a host, given its incus network state."""
        for interface, data in network.items():
            if interface == "lo":
                continue
            for addr in data.get("addresses", []):
                if addr.get("scope") == "global":
                    click.echo(f"{addr['address']:<39} {host} # {interface}")
