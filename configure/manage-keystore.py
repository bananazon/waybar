#!/usr/bin/env python3

from keystore import SecureKeyStore
from pathlib import Path
import click
import sys
import tarfile

context_settings = dict(help_option_names=["-h", "--help"])
DEFAULT_DB = Path.home() / ".local/share/secure_keystore.db"
DEFAULT_KEY = Path.home() / ".local/share/secure_keystore.key"


def write_was_successful(store: SecureKeyStore, service: str, key: str, value: str):
    if not store.key_exists(service=service, key=key):
        return False

    v = store.get(service=service, key=key)
    return True if v == value else False


def get_store(db_path: Path, key_path: Path):
    """Lazy-load the keystore only when needed"""
    return SecureKeyStore(db_path=db_path, key_path=key_path)


@click.group(invoke_without_command=True, context_settings=context_settings)
@click.option(
    "-d",
    "--database",
    default=DEFAULT_DB,
    type=click.Path(),
    help="Path to the database",
)
@click.option(
    "-k",
    "--key",
    default=DEFAULT_KEY,
    type=click.Path(),
    help="Path to the encryption key",
)
@click.pass_context
def cli(ctx: click.Context, database: Path, key: Path):
    ctx.ensure_object(dict)
    ctx.obj["database"] = database
    ctx.obj["key"] = key
    if ctx.invoked_subcommand is None:
        click.echo(cli.get_help(ctx))


# We want to verify set/update (service, key, value)
@cli.command(name="set", help="Store a new key into the keystore")
@click.option(
    "-s", "--service", required=True, help="Name of the service where the key resides"
)
@click.option("-k", "--key", required=True, help="Name of the item")
@click.option("-v", "--value", required=True, help="Item value")
@click.pass_context
def set(ctx: click.Context, service: str, key: str, value: str):
    store = get_store(ctx.obj["database"], ctx.obj["key"])
    if store.key_exists(service=service, key=key):
        click.echo(f'The key "{key}" already exists in the service "{service}"')
    else:
        store.set(service, key, value)
        if write_was_successful(store, service, key, value):
            click.echo(f'Successfully stored key "{key}" in the service "{service}"')
        else:
            click.echo(f'Failed to store key "{key}" in the service "{service}"')
            sys.exit(1)


@cli.command(name="get", help="Retrieve an existing key from the keystore")
@click.option(
    "-s", "--service", required=True, help="Name of the service where the key resides"
)
@click.option("-k", "--key", required=True, help="Name of the item")
@click.pass_context
def get(ctx: click.Context, service: str, key: str):
    store = get_store(ctx.obj["database"], ctx.obj["key"])
    if store.key_exists(service=service, key=key):
        value = store.get(service=service, key=key)
        click.echo(value)
    else:
        click.echo(f'The key "{key}" doesn\'t exist in the service "{service}"')


@cli.command(name="update", help="Update an existing key in the keystore")
@click.option(
    "-s", "--service", required=True, help="Name of the service where the key resides"
)
@click.option("-k", "--key", required=True, help="Name of the item")
@click.option("-v", "--value", required=True, help="Item value")
@click.pass_context
def update(ctx: click.Context, service: str, key: str, value: str):
    store = get_store(ctx.obj["database"], ctx.obj["key"])
    if not store.key_exists(service=service, key=key):
        click.echo(f'The key "{key}" doesn\'t exist in the service "{service}"')
    else:
        store.update(service, key, value)
        if write_was_successful(store, service, key, value):
            click.echo(f'Successfully updated key "{key}" in the service "{service}"')
        else:
            click.echo(f'Failed to update key "{key}" in the service "{service}"')
            sys.exit(1)


@cli.command(name="delete", help="Delete an existing key from the keystore")
@click.option(
    "-s", "--service", required=True, help="Name of the service where the key resides"
)
@click.option("-k", "--key", required=True, help="Name of the item")
@click.pass_context
def delete(ctx: click.Context, service: str, key: str):
    store = get_store(ctx.obj["database"], ctx.obj["key"])
    if not store.key_exists(service=service, key=key):
        click.echo(f'The key "{key}" doesn\'t exist in the service "{service}"')
    else:
        store.delete(service=service, key=key)
        if store.key_exists(service=service, key=key):
            click.echo(f'Failed to delete key "{key}" from the service "{service}"')
            sys.exit(1)
        else:
            click.echo(f'Successfully deleted key "{key}" from the service "{service}"')


@cli.command(name="list-keys", help="List keys for the specified service")
@click.option(
    "-s",
    "--service",
    required=True,
    help="Name of the service you want to list keys for",
)
@click.pass_context
def list_keys(ctx: click.Context, service: str):
    store = get_store(ctx.obj["database"], ctx.obj["key"])
    items = store.list_keys(service)
    keys = "key" if len(items) == 1 else "keys"
    print(f"The service {service} has {len(items)} {keys}")
    for idx, key in enumerate(items):
        click.echo(f"  {idx + 1:02} {key}")


@cli.command(name="list-services", help="List all of the services in the keystore")
@click.pass_context
def list_services(ctx: click.Context):
    store = get_store(ctx.obj["database"], ctx.obj["key"])
    items = store.list_services()
    services = "service" if len(items) == 1 else "services"
    print(f"There are {len(items)} {services} in the keystore")
    for idx, key in enumerate(items):
        click.echo(f"  {idx + 1:02} {key}")


@cli.command(name="export", help="Export the keystore as a tgz file")
@click.argument("backup_file", type=click.Path())
@click.pass_context
def export(ctx: click.Context, backup_file):
    backup_file = Path(backup_file)
    db_path = Path(ctx.obj["database"])
    key_path = Path(ctx.obj["key"])
    with tarfile.open(backup_file, "w:gz") as tar:
        tar.add(db_path, arcname="secure_keystore.db")
        tar.add(key_path, arcname="secure_keystore.key")
    click.echo(f"Keystore exported to {backup_file}")


@cli.command(
    name="import-backup",
    help='Import the keystore from a backup file generated with "export"',
)
@click.argument("backup_file", type=click.Path(exists=True))
@click.pass_context
def import_backup(ctx: click.Context, backup_file):
    backup_file = Path(backup_file)
    db_path = Path(ctx.obj["database"])
    key_path = Path(ctx.obj["key"])
    with tarfile.open(backup_file, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name == "secure_keystore.db":
                tar.extract(member, path=db_path.parent)
                (db_path.parent / "secure_keystore.db").chmod(0o600)
            elif member.name == "secure_keystore.key":
                tar.extract(member, path=key_path.parent)
                (key_path.parent / "secure_keystore.key").chmod(0o600)
    click.echo(f"Keystore imported from {backup_file}")


if __name__ == "__main__":
    cli()
