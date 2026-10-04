"""Secrets provider abstraction preventing hardcoded credentials."""

import os
from pathlib import Path


class SecretsProvider:
    def __init__(self, env_path: Path | None = None) -> None:
        self.env_path = env_path or Path(".env")
        self._dotenv_cache: dict[str, str] = {}
        self._load_dotenv()

    def _load_dotenv(self) -> None:
        if self.env_path.exists():
            for line in self.env_path.read_text().splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key, val = stripped.split("=", 1)
                    clean_val = val.strip().strip("'\"")
                    self._dotenv_cache[key.strip()] = clean_val

    def get_secret(self, key: str, default: str | None = None) -> str:
        # Check environment variable first (standard 12-factor pattern)
        if key in os.environ and os.environ[key].strip():
            return os.environ[key].strip()
        # Check .env cache
        if key in self._dotenv_cache:
            return self._dotenv_cache[key]
        if default is not None:
            return default
        raise KeyError(f"Required secret '{key}' not found in environment or vault.")

    @staticmethod
    def mask(secret: str) -> str:
        if not secret or len(secret) <= 8:
            return "***"
        return f"{secret[:4]}...{secret[-4:]}"


_SECRETS = SecretsProvider()


def get_secret(key: str, default: str | None = None) -> str:
    return _SECRETS.get_secret(key, default)
