from __future__ import annotations

import json
from pathlib import Path


def _index_file(data_dir: str, telegram_user_id: int) -> Path:
    return Path(data_dir) / "bot_users" / f"{telegram_user_id}.json"


def get_linked_phone(data_dir: str, telegram_user_id: int) -> str | None:
    path = _index_file(data_dir, telegram_user_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    phone = payload.get("phone")
    return phone if isinstance(phone, str) and phone else None


def set_linked_phone(data_dir: str, telegram_user_id: int, phone: str) -> None:
    path = _index_file(data_dir, telegram_user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"phone": phone}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_linked_phone(data_dir: str, telegram_user_id: int) -> None:
    path = _index_file(data_dir, telegram_user_id)
    if path.is_file():
        path.unlink()
