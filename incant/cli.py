import click
from incant import Incant


@click.group(invoke_without_command=True)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose mode.")
@click.option("-f", "--config", type=click.Path(exists=True), help="Path to configuration file.")
@click.option(
    "-q", "--quiet", is_flag=True, help="Do not display error message if no config file found."
)
@click.pass_context
def cli(ctx, verbose, config, quiet):
    """Incant -- an Incus frontend for descriptive development environments"""
    ctx.ensure_object(dict)
    ctx.obj["OPTIONS"] = {"verbose": verbose, "config": config, "quiet": quiet}
    if verbose:
        click.echo(
            f"Using config file: {config}" if config else "No config file provided, using defaults."
        )
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())  # Show help message if no command is passed


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def up(ctx, name: str):
    """Start and provision an instance or all instances if no name is provided."""
    inc = Incant(**ctx.obj["OPTIONS"])
    inc.up(name)


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def provision(ctx, name: str = None):
    """Provision an instance or all instances if no name is provided."""
    inc = Incant(**ctx.obj["OPTIONS"])
    inc.provision(name)


@cli.command()
@click.argument("name", required=False)
@click.pass_context
def destroy(ctx, name: str):
    """Destroy an instance or all instances if no name is provided."""
    inc = Incant(**ctx.obj["OPTIONS"])
    inc.destroy(name)


@cli.command()
@click.pass_context
def dump(ctx):
    """Show the generated configuration file."""
    inc = Incant(**ctx.obj["OPTIONS"])
    inc.dump_config()


@cli.command()
@click.pass_context
def list(ctx):
    """List all instances defined in the configuration."""
    inc = Incant(**ctx.obj["OPTIONS"])
    inc.list_instances()
