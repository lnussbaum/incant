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
