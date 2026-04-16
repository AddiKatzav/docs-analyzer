import json
from datetime import UTC, datetime
from threading import Lock

from cryptography.fernet import Fernet

from app.models import ConfigStatusResponse, Provider
from app.services.paths import CONFIG_FILE, SECRET_FILE, ensure_data_dirs

_lock = Lock()


def _load_or_create_key() -> bytes:
    ensure_data_dirs()
    if SECRET_FILE.exists():
        return SECRET_FILE.read_bytes()
    key = Fernet.generate_key()
    SECRET_FILE.write_bytes(key)
    return key


_fernet = Fernet(_load_or_create_key())


def get_config() -> dict | None:
    ensure_data_dirs()
    if not CONFIG_FILE.exists():
        return None
    with _lock:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def get_status() -> ConfigStatusResponse:
    saved = get_config()
    if not saved:
        return ConfigStatusResponse(provider=None, configured=False, updated_at=None)
    updated_at = datetime.fromisoformat(saved["updated_at"])
    return ConfigStatusResponse(
        provider=Provider(saved["provider"]), configured=True, updated_at=updated_at
    )


def save_config(provider: Provider, api_key: str) -> None:
    encrypted = _fernet.encrypt(api_key.encode("utf-8")).decode("utf-8")
    payload = {
        "provider": provider.value,
        "encrypted_api_key": encrypted,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    with _lock:
        CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_decrypted_api_key() -> tuple[Provider, str] | None:
    saved = get_config()
    if not saved:
        return None
    api_key = _fernet.decrypt(saved["encrypted_api_key"].encode("utf-8")).decode("utf-8")
    return Provider(saved["provider"]), api_key
