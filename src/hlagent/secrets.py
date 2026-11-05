import base64
import json
import os
import secrets
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


class SecretVault:
    def __init__(self, home: Path):
        self.path = home / "credentials.encrypted.json"
        self._keys: dict[str, str] = {}
        self._lock = threading.RLock()

    def set(self, provider: str, key: str):
        with self._lock:
            self._keys[provider] = key

    def get(self, provider: str) -> str | None:
        with self._lock:
            return self._keys.get(provider)

    def clear(self):
        with self._lock:
            self._keys.clear()

    @staticmethod
    def cipher(password: str, salt: bytes) -> Fernet:
        if len(password) < 12:
            raise ValueError("Use a vault passphrase of at least 12 characters")
        kdf = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1)
        return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode())))

    def save(self, password: str):
        salt = os.urandom(16)
        with self._lock:
            blob = self.cipher(password, salt).encrypt(json.dumps(self._keys).encode())
        temp = self.path.with_suffix(".partial")
        temp.write_text(json.dumps({"salt": base64.b64encode(salt).decode(), "payload": blob.decode()}))
        temp.chmod(0o600)
        temp.replace(self.path)

    def unlock(self, password: str):
        data = json.loads(self.path.read_text())
        try:
            keys = json.loads(self.cipher(password, base64.b64decode(data["salt"])).decrypt(data["payload"].encode()))
        except InvalidToken as exc:
            raise ValueError("Incorrect passphrase or damaged vault") from exc
        with self._lock:
            self._keys.update(keys)


def api_token(home: Path) -> str:
    path = home / ".api-token"
    if not path.exists():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
    return path.read_text().strip()
