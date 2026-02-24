"""Application settings."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8787
    debug: bool = False
    frontend_dir: Path = Path(__file__).resolve().parent.parent / "frontend"
    snapshot_mount_base: Path = Path.home() / ".recover-jerry" / "snapshots"
    recovery_default_dir: Path = Path.home() / "Desktop" / "recovered-files"
    max_preview_size_mb: int = 50

    model_config = {"env_prefix": "JERRY_"}


settings = Settings()
