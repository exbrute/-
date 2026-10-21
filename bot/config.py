import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    api_id: int
    api_hash: str
    sessions_dir: str
    tdata_dir: str
    data_dir: str


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    api_id_raw = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    sessions_dir = os.getenv("SESSIONS_DIR", "sessions").strip() or "sessions"
    tdata_dir = os.getenv("TDATA_DIR", "tdata").strip() or "tdata"
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"

    missing = []
    if not token:
        missing.append("BOT_TOKEN")
    if not api_id_raw:
        missing.append("API_ID")
    if not api_hash:
        missing.append("API_HASH")
    if missing:
        raise RuntimeError(
            f"Задайте переменные окружения: {', '.join(missing)} (см. .env.example)"
        )

    return Settings(
        bot_token=token,
        api_id=int(api_id_raw),
        api_hash=api_hash,
        sessions_dir=sessions_dir,
        tdata_dir=tdata_dir,
        data_dir=data_dir,
    )
