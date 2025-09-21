#!/usr/bin/env python3

from cryptography.fernet import Fernet
from pathlib import Path
import base64
import click
import os
import shutil
import sqlite3
import tarfile
# enforce cryptography, click

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
DEFAULT_DB = Path.home() / ".local/share/secure_keystore.db"
DEFAULT_KEY = Path.home() / ".local/share/secure_keystore.key"

class SecureKeyStore:
    def __init__(self, db_path=None, key_path=None):
        self.db_path = Path(db_path or Path.home() / ".local/share/secure_keystore.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.key_path = Path(key_path or Path.home() / ".local/share/secure_keystore.key")
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

        # Load or generate encryption key
        if self.key_path.exists():
            key = self.key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
            self.key_path.chmod(0o600)  # restrict access

        self.fernet = Fernet(key)

        # Setup DB
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS secrets (
                service TEXT NOT NULL,
                key TEXT NOT NULL,
                value BLOB,
                PRIMARY KEY (service, key)
            )
        """)
        self.conn.commit()

    def set(self, service, key, value):
        encrypted = self.fernet.encrypt(value.encode())
        self.conn.execute(
            "INSERT OR REPLACE INTO secrets(service,key,value) VALUES (?,?,?)",
            (service, key, encrypted)
        )
        self.conn.commit()

    def get(self, service, key):
        cursor = self.conn.execute(
            "SELECT value FROM secrets WHERE service=? AND key=?",
            (service, key)
        )
        row = cursor.fetchone()
        return self.fernet.decrypt(row[0]).decode() if row else None

    def update(self, service, key, value):
        if self.get(service, key) is None:
            raise KeyError(f"{service}/{key} does not exist")
        self.set(service, key, value)

    def delete(self, service, key):
        self.conn.execute(
            "DELETE FROM secrets WHERE service=? AND key=?",
            (service, key)
        )
        self.conn.commit()

    def list_keys(self, service=None):
        if service:
            cursor = self.conn.execute(
                "SELECT key FROM secrets WHERE service=?",
                (service,)
            )
        else:
            cursor = self.conn.execute("SELECT service, key FROM secrets")
        return [row[0] if service else f"{row[0]}/{row[1]}" for row in cursor.fetchall()]
    
    # Convenience methods
    def service_exists(self, service=None):
        if service:
            cursor = self.conn.execute(
                'SELECT count(*) FROM secrets WHERE service=?',
                (service,),
            )
            (count,) = cursor.fetchone()
            return True if count > 0 else False
        return None

    def key_exists(self, service=None, key=None):
        if service and key:
            cursor = self.conn.execute(
                'SELECT count(*) FROM secrets WHERE service=? AND key=?',
                (service, key, ),
            )
            (count,) = cursor.fetchone()
            return True if count > 0 else False
        return None

def write_was_successful(store, service, key, value):
    if not store.key_exists(service, key):
        return False

    v = store.get(service, key)
    return True if v == value else False

def get_store(db_path, key_path):
    """Lazy-load the keystore only when needed."""
    return SecureKeyStore(db_path=db_path, key_path=key_path)

@click.group(invoke_without_command=True, context_settings=CONTEXT_SETTINGS)
@click.option("--db", default=DEFAULT_DB, type=click.Path(), help="Path to DB")
@click.option("--key", default=DEFAULT_KEY, type=click.Path(), help="Path to encryption key")
@click.pass_context
def cli(ctx, db, key):
    """Secure KeyStore CLI"""
    ctx.ensure_object(dict)
    ctx.obj['db'] = db
    ctx.obj['key'] = key
    if ctx.invoked_subcommand is None:
        click.echo(cli.get_help(ctx))

# -----------------------
# Core commands
# -----------------------

# We want to verify set/update (service, key, value)
@cli.command(name='set', help='Store a new key into the keystore')
@click.option('-s', '--service', required=True, help='Name of the service where the key resides')
@click.option('-k', '--key', required=True, help='Name of the item')
@click.option('-v', '--value', required=True, help='Item value')
@click.pass_context
def set(ctx, service, key, value):
    store = get_store(ctx.obj['db'], ctx.obj['key'])
    if store.key_exists(service, key):
        click.echo(f'The key "{key}" already exists in the service "{service}"')
    else:
        store.set(service, key, value)
        if write_was_successful(store, service, key, value):
            click.echo(f'Successfully stored key "{key}" in the service "{service}"')
        else:
            click.echo(f'Failed to store key "{key}" in the service "{service}"')   
            sys.exit(1)         

@cli.command(name='get', help='Retrieve an existing key from the keystore')
@click.option('-s', '--service', required=True, help='Name of the service where the key resides')
@click.option('-k', '--key', required=True, help='Name of the item')
@click.pass_context
def get(ctx, service, key):
    store = get_store(ctx.obj['db'], ctx.obj['key'])
    if store.key_exists(service, key):
        value = store.get(service, key)
        click.echo(value)
    else:
        click.echo(f'The key "{key}" doesn\'t exist in the service "{service}"')

@cli.command(name='update', help='Update an existing key in the keystore')
@click.option('-s', '--service', required=True, help='Name of the service where the key resides')
@click.option('-k', '--key', required=True, help='Name of the item')
@click.option('-v', '--value', required=True, help='Item value')
@click.pass_context
def update(ctx, service, key, value):
    store = get_store(ctx.obj['db'], ctx.obj['key'])
    if not store.key_exists(service, key):
        click.echo(f'The key "{key}" doesn\'t exist in the service "{service}"')
    else:
        store.update(service, key, value)
        if write_was_successful(store, service, key, value):
            click.echo(f'Successfully updated key "{key}" in the service "{service}"')
        else:
            click.echo(f'Failed to update key "{key}" in the service "{service}"') 
            sys.exit(1)

@cli.command(name='delete', help='Delete an existing key from the keystore')
@click.option('-s', '--service', required=True, help='Name of the service where the key resides')
@click.option('-k', '--key', required=True, help='Name of the item')
@click.pass_context
def delete(ctx, service, key):
    store = get_store(ctx.obj['db'], ctx.obj['key'])
    if not store.key_exists(service, key):
        click.echo(f'The key "{key}" doesn\'t exist in the service "{service}"')
    else:
        store.delete(service, key)
        if store.key_exists(service, key):
             click.echo(f'Failed to delete key "{key}" from the service "{service}"')
             sys.exit(1)
        else:
            click.echo(f'Successfully deleted key "{key}" from the service "{service}"')

@cli.command(name='list', help='List keys for the specified service')
@click.option('-s', '--service', required=True, help='Name of the service you want to list keys for')
@click.pass_context
def list_keys(ctx, service):
    store = get_store(ctx.obj['db'], ctx.obj['key'])
    items = store.list_keys(service)
    keys = 'key' if len(items) == 1 else 'keys'
    print(f'The service {service} has {len(items)} {keys}')
    for idx, key in enumerate(items):
        click.echo(f'  {idx+1:02} {key}')



@cli.command(name='dummy', help='I am a dummy')
@click.option('-s', '--service', required=False, help='Name of the service where the key resides')
@click.option('-k', '--key', required=False, help='Name of the item')
@click.option('-v', '--value', required=False, help='Item value')
@click.pass_context
def dummy(ctx, service, key, value):
    store = get_store(ctx.obj['db'], ctx.obj['key'])
    print(store.service_exists(service))
    print(store.key_exists(service, key))

# -----------------------
# Backup commands
# -----------------------

@cli.command()
@click.argument("backup_file", type=click.Path())
@click.pass_context
def export(ctx, backup_file):
    """Export keystore (DB + key) to a single archive"""
    backup_file = Path(backup_file)
    db_path = Path(ctx.obj['db'])
    key_path = Path(ctx.obj['key'])
    with tarfile.open(backup_file, "w:gz") as tar:
        tar.add(db_path, arcname="secure_keystore.db")
        tar.add(key_path, arcname="secure_keystore.key")
    click.echo(f"Keystore exported to {backup_file}")

@cli.command(name="import-backup")
@click.argument("backup_file", type=click.Path(exists=True))
@click.pass_context
def import_backup(ctx, backup_file):
    """Import keystore from backup archive"""
    backup_file = Path(backup_file)
    db_path = Path(ctx.obj['db'])
    key_path = Path(ctx.obj['key'])
    with tarfile.open(backup_file, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name == "secure_keystore.db":
                tar.extract(member, path=db_path.parent)
                (db_path.parent / "secure_keystore.db").chmod(0o600)
            elif member.name == "secure_keystore.key":
                tar.extract(member, path=key_path.parent)
                (key_path.parent / "secure_keystore.key").chmod(0o600)
    click.echo(f"Keystore imported from {backup_file}")

# -----------------------
if __name__ == "__main__":
    cli()
