import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet

context_settings = dict(help_option_names=["-h", "--help"])
DEFAULT_DB = Path.home() / ".local/share/secure_keystore.db"
DEFAULT_KEY = Path.home() / ".local/share/secure_keystore.key"


class SecureKeyStore:
    fernet: Fernet
    conn: sqlite3.Connection
    db_path: Path
    key_path: Path

    def __init__(self, db_path: Path, key_path: Path):
        self.db_path = Path(db_path or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.key_path = Path(key_path or DEFAULT_KEY)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

        # Load or generate encryption key
        if self.key_path.exists():
            key = self.key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            _ = self.key_path.write_bytes(key)
            self.key_path.chmod(0o600)  # restrict access

        self.fernet = Fernet(key)

        # Setup DB
        self.conn = sqlite3.connect(self.db_path)
        _ = self.conn.execute("""
            CREATE TABLE IF NOT EXISTS secrets (
                service TEXT NOT NULL,
                key TEXT NOT NULL,
                value BLOB,
                PRIMARY KEY (service, key)
            )
        """)
        self.conn.commit()

    def set(self, service: str, key: str, value: str) -> None:
        encrypted = self.fernet.encrypt(value.encode())
        _ = self.conn.execute(
            "INSERT OR REPLACE INTO secrets(service,key,value) VALUES (?,?,?)",
            (service, key, encrypted),
        )
        self.conn.commit()

    def get(self, service: str, key: str) -> str | None:
        cursor = self.conn.execute(
            "SELECT value FROM secrets WHERE service=? AND key=?", (service, key)
        )
        row = cursor.fetchone()
        return self.fernet.decrypt(row[0]).decode() if row else None

    def update(self, service: str, key: str, value: str):
        if self.get(service, key) is None:
            raise KeyError(f"{service}/{key} does not exist")
        self.set(service, key, value)

    def delete(self, service: str, key: str):
        _ = self.conn.execute(
            "DELETE FROM secrets WHERE service=? AND key=?", (service, key)
        )
        self.conn.commit()

    def list_services(self):
        cursor = self.conn.execute(
            "SELECT DISTINCT service FROM secrets ORDER BY service"
        )
        return [row[0] for row in cursor.fetchall()]
        # return cursor.fetchall()

    def list_keys(self, service: str):
        if service:
            cursor = self.conn.execute(
                "SELECT key FROM secrets WHERE service=?", (service,)
            )
        else:
            cursor = self.conn.execute("SELECT service, key FROM secrets")
        return [row[0] for row in cursor.fetchall()]

    # Convenience methods
    def service_exists(self, service: str):
        if service:
            cursor = self.conn.execute(
                "SELECT count(*) FROM secrets WHERE service=?",
                (service,),
            )
            (count,) = cursor.fetchone()
            return True if count > 0 else False
        return None

    def key_exists(self, service: str, key: str):
        if service and key:
            cursor = self.conn.execute(
                "SELECT count(*) FROM secrets WHERE service=? AND key=?",
                (
                    service,
                    key,
                ),
            )
            (count,) = cursor.fetchone()
            return True if count > 0 else False
        return None
