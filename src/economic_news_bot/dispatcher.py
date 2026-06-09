import json
import os
import time
from pathlib import Path
from typing import Iterable, List, Tuple

from .models import BuiltCardSet


def dispatch_card_sets(card_sets: Iterable[BuiltCardSet], dry_run: bool = False, delay_seconds: float = 3.0) -> None:
    card_sets = list(card_sets)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID")

    if dry_run or not token or not channel_id:
        if not dry_run:
            print("[DRY-RUN] TELEGRAM_BOT_TOKEN/CHANNEL_ID missing; dispatch skipped.")
        else:
            print("[DRY-RUN] Telegram dispatch skipped.")
        for card_set in card_sets:
            headline = card_set.caption.splitlines()[0] if card_set.caption else ""
            print("  rank {} -> {} files | {}".format(card_set.rank, len(card_set.files), headline))
        return

    try:
        import requests  # type: ignore
    except ImportError as exc:
        raise RuntimeError("requests is required for Telegram dispatch.") from exc

    for index, card_set in enumerate(card_sets):
        if index:
            time.sleep(delay_seconds)
        _post_with_retry(requests, token, channel_id, card_set)
        print("[SENT] rank {} ({} files)".format(card_set.rank, len(card_set.files)))


def notify_admin(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    admin_chat_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
    if not token or not admin_chat_id:
        print("[INFO] Admin notification skipped: {}".format(message))
        return

    try:
        import requests  # type: ignore

        url = "https://api.telegram.org/bot{}/sendMessage".format(token)
        response = requests.post(url, data={"chat_id": admin_chat_id, "text": message}, timeout=20)
        response.raise_for_status()
    except Exception as exc:  # never let admin notification mask the real result
        print("[WARN] Admin notification failed ({}): {}".format(exc, message))


def _build_media(card_set: BuiltCardSet) -> Tuple[List[dict], dict]:
    media = []
    files = {}
    for idx, file_path in enumerate(card_set.files):
        field_name = "file{}".format(idx)
        item = {"type": "photo", "media": "attach://{}".format(field_name)}
        if idx == len(card_set.files) - 1:
            item["caption"] = card_set.caption
        media.append(item)
        files[field_name] = Path(file_path).open("rb")
    return media, files


def _post_with_retry(requests, token: str, channel_id: str, card_set: BuiltCardSet, attempts: int = 4) -> None:
    url = "https://api.telegram.org/bot{}/sendMediaGroup".format(token)
    last_error = None

    for attempt in range(1, attempts + 1):
        media, files = _build_media(card_set)
        data = {"chat_id": channel_id, "media": json.dumps(media, ensure_ascii=False)}
        try:
            response = requests.post(url, data=data, files=files, timeout=60)
        except requests.exceptions.RequestException as exc:
            last_error = "network error: {}".format(exc)
            response = None
        finally:
            for handle in files.values():
                handle.close()

        if response is not None:
            if response.ok:
                return
            payload = _safe_json(response)
            description = payload.get("description", response.text[:200])
            retry_after = payload.get("parameters", {}).get("retry_after")
            last_error = "Telegram API status {}: {}".format(response.status_code, description)
            retriable = response.status_code == 429 or response.status_code >= 500
            if not (retriable and attempt < attempts):
                break
            wait_seconds = int(retry_after) + 1 if retry_after else min(30, 3 * attempt)
        else:
            if attempt >= attempts:
                break
            wait_seconds = min(30, 3 * attempt)

        print("[WARN] rank {} send failed ({}); retrying in {}s.".format(card_set.rank, last_error, wait_seconds))
        time.sleep(wait_seconds)

    raise RuntimeError(last_error or "Telegram API failed.")


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}
