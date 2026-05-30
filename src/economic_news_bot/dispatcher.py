import json
import os
import time
from pathlib import Path
from typing import Iterable

from .models import BuiltCardSet


def dispatch_card_sets(card_sets: Iterable[BuiltCardSet], dry_run: bool = False, delay_seconds: float = 3.0) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID")

    if dry_run or not token or not channel_id:
        print("[DRY-RUN] Telegram dispatch skipped.")
        for card_set in card_sets:
            print("  rank {} -> {} files, caption={!r}".format(card_set.rank, len(card_set.files), card_set.caption))
        return

    try:
        import requests  # type: ignore
    except ImportError as exc:
        raise RuntimeError("requests is required for Telegram dispatch.") from exc

    for index, card_set in enumerate(card_sets):
        if index:
            time.sleep(delay_seconds)
        _send_media_group(requests, token, channel_id, card_set)


def notify_admin(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    admin_chat_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
    if not token or not admin_chat_id:
        print("[INFO] Admin notification skipped: {}".format(message))
        return

    try:
        import requests  # type: ignore
    except ImportError:
        print("[INFO] Admin notification skipped because requests is missing: {}".format(message))
        return

    url = "https://api.telegram.org/bot{}/sendMessage".format(token)
    response = requests.post(url, data={"chat_id": admin_chat_id, "text": message}, timeout=20)
    response.raise_for_status()


def _send_media_group(requests, token: str, channel_id: str, card_set: BuiltCardSet) -> None:
    url = "https://api.telegram.org/bot{}/sendMediaGroup".format(token)
    media = []
    files = {}

    for idx, file_path in enumerate(card_set.files):
        path = Path(file_path)
        field_name = "file{}".format(idx)
        item = {"type": "photo", "media": "attach://{}".format(field_name)}
        if idx == len(card_set.files) - 1:
            item["caption"] = card_set.caption
        media.append(item)
        files[field_name] = path.open("rb")

    try:
        _post_with_retry(requests, url, {"chat_id": channel_id, "media": json.dumps(media, ensure_ascii=False)}, files)
    finally:
        for handle in files.values():
            handle.close()


def _post_with_retry(requests, url: str, data: dict, files: dict, attempts: int = 4) -> None:
    last_error = None
    for attempt in range(1, attempts + 1):
        response = requests.post(url, data=data, files=files, timeout=45)
        if response.ok:
            return

        payload = _safe_json(response)
        description = payload.get("description", response.text[:200])
        retry_after = payload.get("parameters", {}).get("retry_after")
        if response.status_code == 429 and retry_after and attempt < attempts:
            wait_seconds = int(retry_after) + 1
            print("[WARN] Telegram rate limit hit; waiting {}s before retry.".format(wait_seconds))
            time.sleep(wait_seconds)
            for handle in files.values():
                handle.seek(0)
            continue

        last_error = "Telegram API failed with status {}: {}".format(response.status_code, description)
        break

    raise RuntimeError(last_error or "Telegram API failed.")


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}
