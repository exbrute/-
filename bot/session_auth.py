from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from opentele.api import UseCurrentSession
from opentele.tl import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw.strip())
    if not digits:
        raise ValueError("Номер пустой")
    if raw.strip().startswith("+"):
        return "+" + digits
    if digits.startswith("8") and len(digits) == 11:
        return "+7" + digits[1:]
    return "+" + digits


def session_base_name(telegram_user_id: int) -> str:
    return f"demo_{telegram_user_id}"


def session_file_path(workdir: str, telegram_user_id: int) -> Path:
    return Path(workdir) / f"{session_base_name(telegram_user_id)}.session"


def session_stem_path(workdir: str, telegram_user_id: int) -> Path:
    """Путь без расширения — так Telethon создаёт `.session` рядом."""
    return Path(workdir) / session_base_name(telegram_user_id)


def tdata_dir_path(workdir: str, telegram_user_id: int) -> Path:
    return Path(workdir) / f"{session_base_name(telegram_user_id)}_tdata"


def remove_user_artifacts(workdir: str, telegram_user_id: int) -> None:
    session = session_file_path(workdir, telegram_user_id)
    for candidate in (session, Path(f"{session}-journal")):
        if candidate.is_file():
            candidate.unlink()

    tdata = tdata_dir_path(workdir, telegram_user_id)
    if tdata.is_dir():
        shutil.rmtree(tdata)


@dataclass
class PendingLogin:
    phone: str
    client: TelegramClient


async def create_connected_client(
    api_id: int, api_hash: str, workdir: str, telegram_user_id: int
) -> TelegramClient:
    Path(workdir).mkdir(parents=True, exist_ok=True)
    client = TelegramClient(
        str(session_stem_path(workdir, telegram_user_id)),
        api_id,
        api_hash,
    )
    await client.connect()
    return client


async def start_login(
    api_id: int,
    api_hash: str,
    workdir: str,
    telegram_user_id: int,
    phone_raw: str,
) -> PendingLogin:
    phone = normalize_phone(phone_raw)
    client = await create_connected_client(
        api_id, api_hash, workdir, telegram_user_id
    )
    if await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("already_authorized")

    await client.send_code_request(phone)
    return PendingLogin(phone=phone, client=client)


async def complete_code(pending: PendingLogin, code_raw: str) -> str | None:
    code = re.sub(r"\s", "", code_raw.strip())
    try:
        await pending.client.sign_in(pending.phone, code)
    except SessionPasswordNeededError:
        return "password"
    except PhoneCodeInvalidError:
        raise ValueError("invalid_code")
    except PhoneCodeExpiredError:
        raise ValueError("expired_code")
    return None


async def complete_password(pending: PendingLogin, password: str) -> None:
    try:
        await pending.client.sign_in(password=password.strip())
    except PasswordHashInvalidError:
        raise ValueError("invalid_password")


async def export_tdata(client: TelegramClient, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tdesk = await client.ToTDesktop(flag=UseCurrentSession)
    tdesk.SaveTData(str(dest))


async def finalize_login(
    pending: PendingLogin, workdir: str, telegram_user_id: int
) -> tuple[Path, Path]:
    tdata = tdata_dir_path(workdir, telegram_user_id)
    await export_tdata(pending.client, tdata)
    await disconnect_quiet(pending.client)
    return session_file_path(workdir, telegram_user_id), tdata


async def disconnect_quiet(client: TelegramClient | None) -> None:
    if client is None:
        return
    try:
        if client.is_connected():
            await client.disconnect()
    except Exception:
        pass
