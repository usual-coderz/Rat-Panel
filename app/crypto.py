from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_fernet = Fernet(settings.fernet_key.encode())


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("FERNET_KEY mismatch") from exc


def mask(value: str, keep: int = 6) -> str:
    return "•" * 8 + value[-keep:] if len(value) > keep else "•" * len(value)