import sys
import click
from incant import Incant
from .exceptions import IncantError
from .constants import CLICK_STYLE


@click.group(invoke_without_command=True)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose mode.")
@click.option("-f", "--config", type=click.Path(exists=True), help="Path to configuration file.")
@click.pass_context
def cli(ctx, verbose, config):
    """Incant -- an Incus frontend for declarative development environments"""
    ctx.ensure_object(dict)
    ctx.obj["OPTIONS"] = {"verbose": verbose, "config": config}
    if verbose:
        click.echo(
            f"Using config file: {config}" if config else "No config file provided, using defaults."
        )
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())  # Show help message if no command is passed


def _handle_error(error: Exception) -> None:
    """Handle errors consistently across operations."""
    if isinstance(error, IncantError):
        click.secho(f"Error: {error}", **CLICK_STYLE["error"])
    else:
        click.secho(f"An unexpected error occurred: {error}", **CLICK_STYLE["error"])
    sys.exit(1)


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def up(ctx, name: str):
    """Start and provision an instance or all instances if no name is provided."""
    try:
        inc = Incant(**ctx.obj["OPTIONS"])
        inc.up(name)
    except IncantError as e:
        _handle_error(e)


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def provision(ctx, name: str = None):
    """Provision an instance or all instances if no name is provided."""
    try:
        inc = Incant(**ctx.obj["OPTIONS"])
        inc.provision(name)
    except IncantError as e:
        _handle_error(e)


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def shell(ctx, name: str):
    """Open a shell into an instance. If no name is given and there is only one instance, use it."""
    try:
        inc = Incant(**ctx.obj["OPTIONS"])
        inc.shell(name)
    except IncantError as e:
        _handle_error(e)


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def destroy(ctx, name: str):
    """Destroy an instance or all instances if no name is provided."""
    try:
        inc = Incant(**ctx.obj["OPTIONS"])
        inc.destroy(name)
    except IncantError as e:
        _handle_error(e)


@cli.command()
@click.pass_context
def dump(ctx):
    """Show the generated configuration file."""
    try:
        inc = Incant(**ctx.obj["OPTIONS"])
        inc.dump_config()
    except IncantError as e:
        _handle_error(e)


@cli.command(name="list")
@click.pass_context
def _list_command(ctx):
    """List all instances defined in the configuration."""
    try:
        inc = Incant(**ctx.obj["OPTIONS"])
        inc.list_instances()
    except IncantError as e:
        _handle_error(e)


@cli.command()
@click.pass_context
def init(ctx):
    """Create an example configuration file in the current directory."""
    try:
        inc = Incant(**ctx.obj["OPTIONS"], no_config=True)
        inc.incant_init()
    except IncantError as e:
        _handle_error(e)
