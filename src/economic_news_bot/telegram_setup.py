import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

from .config import read_env_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Telegram bot setup without exposing secrets.")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--drop-webhook", action="store_true")
    parser.add_argument("--get-updates", action="store_true")
    parser.add_argument("--send-admin-test", action="store_true")
    parser.add_argument("--send-channel-test", action="store_true")
    parser.add_argument("--capture-ids", action="store_true", help="Save private and channel chat IDs from recent updates into .env.")
    args = parser.parse_args()

    read_env_file(args.env)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN is empty. Put it in .env first.")
        return 2

    print("token={}".format(_mask(token)))
    get_me = _api(token, "getMe")
    _print_result("getMe", get_me, keep=("id", "is_bot", "first_name", "username"))
    if not get_me.get("ok"):
        return 1

    webhook = _api(token, "getWebhookInfo")
    _print_webhook(webhook)

    if args.drop_webhook:
        result = _api(token, "deleteWebhook", {"drop_pending_updates": "true"})
        _print_result("deleteWebhook", result)

    if args.get_updates:
        result = _api(token, "getUpdates", {"timeout": "1", "limit": "5", "allowed_updates": json.dumps(["message", "channel_post"])})
        _print_updates(result)
        if args.capture_ids:
            _capture_ids(args.env, result)

    if args.send_admin_test:
        chat_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "").strip()
        if not chat_id:
            print("TELEGRAM_ADMIN_CHAT_ID is empty; cannot send admin test.")
        else:
            result = _api(token, "sendMessage", {"chat_id": chat_id, "text": "경제야 뭐했니 관리자 DM 테스트"})
            _print_result("sendAdminTest", result)

    if args.send_channel_test:
        channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
        if not channel_id:
            print("TELEGRAM_CHANNEL_ID is empty; cannot send channel test.")
        else:
            result = _api(token, "sendMessage", {"chat_id": channel_id, "text": "경제야 뭐했니 채널 발송 테스트"})
            _print_result("sendChannelTest", result)

    return 0


def _api(token: str, method: str, params=None):
    query = urllib.parse.urlencode(params or {})
    url = "https://api.telegram.org/bot{}/{}".format(token, method)
    if query:
        url = "{}?{}".format(url, query)
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"ok": False, "error_code": exc.code, "description": body}
    except Exception as exc:
        return {"ok": False, "description": str(exc)}


def _print_result(label: str, result: dict, keep=None) -> None:
    if result.get("ok") and keep and isinstance(result.get("result"), dict):
        payload = {key: result["result"].get(key) for key in keep}
        print("{}: ok {}".format(label, json.dumps(payload, ensure_ascii=False)))
    elif result.get("ok"):
        print("{}: ok".format(label))
    else:
        print("{}: failed {} {}".format(label, result.get("error_code", ""), result.get("description", "")))


def _print_webhook(result: dict) -> None:
    if not result.get("ok"):
        _print_result("getWebhookInfo", result)
        return
    info = result.get("result", {})
    safe = {
        "url_set": bool(info.get("url")),
        "pending_update_count": info.get("pending_update_count"),
        "last_error_date": info.get("last_error_date"),
        "last_error_message": info.get("last_error_message"),
    }
    print("getWebhookInfo: ok {}".format(json.dumps(safe, ensure_ascii=False)))


def _print_updates(result: dict) -> None:
    if not result.get("ok"):
        _print_result("getUpdates", result)
        return
    updates = result.get("result", [])
    print("getUpdates: ok {} update(s)".format(len(updates)))
    for update in updates:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        if chat:
            safe = {
                "chat_id": chat.get("id"),
                "type": chat.get("type"),
                "title": chat.get("title"),
                "username": chat.get("username"),
                "text": message.get("text"),
            }
            print("  {}".format(json.dumps(safe, ensure_ascii=False)))


def _capture_ids(env_path: str, result: dict) -> None:
    if not result.get("ok"):
        return

    admin_chat_id = ""
    channel_id = ""
    for update in result.get("result", []):
        message = update.get("message") or {}
        channel_post = update.get("channel_post") or {}
        if message:
            chat = message.get("chat") or {}
            if chat.get("type") == "private":
                admin_chat_id = str(chat.get("id") or "")
        if channel_post:
            chat = channel_post.get("chat") or {}
            if chat.get("type") == "channel":
                channel_id = str(chat.get("id") or "")

    changes = {}
    if admin_chat_id:
        changes["TELEGRAM_ADMIN_CHAT_ID"] = admin_chat_id
    if channel_id:
        changes["TELEGRAM_CHANNEL_ID"] = channel_id

    if not changes:
        print("captureIds: no private/channel chat IDs found in recent updates.")
        return

    _update_env_file(env_path, changes)
    print("captureIds: saved {}".format(", ".join(sorted(changes.keys()))))


def _update_env_file(path: str, changes: dict) -> None:
    existing = {}
    order = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle.read().splitlines():
                if "=" not in raw_line or raw_line.strip().startswith("#"):
                    continue
                key, value = raw_line.split("=", 1)
                key = key.strip()
                existing[key] = value
                order.append(key)

    for key, value in changes.items():
        existing[key] = value
        if key not in order:
            order.append(key)

    required = ["GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID", "TELEGRAM_ADMIN_CHAT_ID"]
    for key in required:
        if key not in order:
            order.append(key)
        existing.setdefault(key, "")

    with open(path, "w", encoding="utf-8") as handle:
        for key in order:
            handle.write("{}={}\n".format(key, existing.get(key, "")))


def _mask(value: str) -> str:
    if len(value) <= 10:
        return "***"
    return "{}...{}".format(value[:6], value[-4:])


if __name__ == "__main__":
    sys.exit(main())
