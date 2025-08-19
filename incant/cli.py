import sys
import click
from incant import Incant
from .exceptions import IncantError
from .reporter import Reporter


@click.group(invoke_without_command=True)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose mode.")
@click.option("-f", "--config", type=click.Path(exists=True), help="Path to configuration file.")
@click.pass_context
def cli(ctx, verbose, config):
    """Incant -- an Incus frontend for declarative development environments"""
    ctx.ensure_object(dict)
    reporter = Reporter()
    ctx.obj["REPORTER"] = reporter
    ctx.obj["OPTIONS"] = {"verbose": verbose, "config": config}

    if verbose:
        reporter.info(
            f"Using config file: {config}" if config else "No config file provided, using defaults."
        )
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _handle_error(error: Exception, reporter: Reporter) -> None:
    """Handle errors consistently across operations."""
    if isinstance(error, IncantError):
        reporter.error(f"Error: {error}")
    else:
        reporter.error(f"An unexpected error occurred: {error}")
    sys.exit(1)


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def up(ctx, name: str):
    """Start and provision an instance or all instances if no name is provided."""
    try:
        Incant(reporter=ctx.obj["REPORTER"], **ctx.obj["OPTIONS"]).up(name)
    except IncantError as e:
        _handle_error(e, ctx.obj["REPORTER"])


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def provision(ctx, name: str = None):
    """Provision an instance or all instances if no name is provided."""
    try:
        Incant(reporter=ctx.obj["REPORTER"], **ctx.obj["OPTIONS"]).provision(name)
    except IncantError as e:
        _handle_error(e, ctx.obj["REPORTER"])


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def shell(ctx, name: str):
    """Open a shell into an instance. If no name is given and there is only one instance, use it."""
    try:
        Incant(reporter=ctx.obj["REPORTER"], **ctx.obj["OPTIONS"]).shell(name)
    except IncantError as e:
        _handle_error(e, ctx.obj["REPORTER"])


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def destroy(ctx, name: str):
    """Destroy an instance or all instances if no name is provided."""
    try:
        Incant(reporter=ctx.obj["REPORTER"], **ctx.obj["OPTIONS"]).destroy(name)
    except IncantError as e:
        _handle_error(e, ctx.obj["REPORTER"])


@cli.command()
@click.pass_context
def dump(ctx):
    """Show the generated configuration file."""
    try:
        Incant(reporter=ctx.obj["REPORTER"], **ctx.obj["OPTIONS"]).dump_config()
    except IncantError as e:
        _handle_error(e, ctx.obj["REPORTER"])


@cli.command(name="list")
@click.option("--no-error", is_flag=True, help="Do not error if no configuration is found.")
@click.pass_context
def _list_command(ctx, no_error: bool):
    """List all instances defined in the configuration."""
    try:
        Incant(reporter=ctx.obj["REPORTER"], no_config=True, **ctx.obj["OPTIONS"]).list_instances(
            no_error=no_error
        )
    except IncantError as e:
        _handle_error(e, ctx.obj["REPORTER"])


@cli.command()
@click.pass_context
def init(ctx):
    """Create an example configuration file in the current directory."""
    try:
        inc = Incant(reporter=ctx.obj["REPORTER"], no_config=True)
        inc.incant_init()
    except IncantError as e:
        _handle_error(e, ctx.obj["REPORTER"])
