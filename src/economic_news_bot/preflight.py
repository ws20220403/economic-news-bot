import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from .config import load_config, read_env_file
from .rss_fetcher import fetch_candidates


REQUIRED_ENV = (
    "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "TELEGRAM_ADMIN_CHAT_ID",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate runtime setup without printing secrets.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--skip-gemini", action="store_true")
    args = parser.parse_args()

    read_env_file(args.env)
    config = load_config(args.config)

    failures = []
    failures.extend(_check_env())
    failures.extend(_check_rss(config))
    failures.extend(_check_telegram())
    if not args.skip_gemini:
        failures.extend(_check_gemini(config))

    if failures:
        print("preflight: failed")
        for failure in failures:
            print("  - {}".format(failure))
        return 1

    print("preflight: ok")
    return 0


def _check_env():
    failures = []
    for key in REQUIRED_ENV:
        if not os.environ.get(key, "").strip():
            failures.append("{} is missing".format(key))
    return failures


def _check_rss(config):
    try:
        candidates = fetch_candidates(config)
    except Exception as exc:
        return ["RSS fetch failed: {}".format(exc)]
    if not candidates:
        return ["RSS fetch returned no candidates"]
    print("rss: ok {} candidate(s)".format(len(candidates)))
    return []


def _check_telegram():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    admin_chat_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "").strip()
    if not token:
        return []

    failures = []
    get_me = _telegram_api(token, "getMe")
    if not get_me.get("ok"):
        failures.append("Telegram getMe failed: {}".format(get_me.get("description", "unknown error")))
    else:
        result = get_me.get("result", {})
        print("telegram bot: ok @{}".format(result.get("username", "")))

    if channel_id:
        chat = _telegram_api(token, "getChat", {"chat_id": channel_id})
        if not chat.get("ok"):
            failures.append("Telegram channel getChat failed: {}".format(chat.get("description", "unknown error")))
        else:
            title = (chat.get("result") or {}).get("title", "")
            print("telegram channel: ok {}".format(title))

    if admin_chat_id:
        admin = _telegram_api(token, "getChat", {"chat_id": admin_chat_id})
        if not admin.get("ok"):
            failures.append("Telegram admin getChat failed: {}".format(admin.get("description", "unknown error")))
        else:
            print("telegram admin: ok")

    return failures


def _check_gemini(config):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return []
    model = config.get("model", "gemini-2.5-flash")
    url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(model)
    payload = {
        "contents": [{"parts": [{"text": "Return only this JSON: {\"ok\": true}"}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return ["Gemini API failed: HTTP {} {}".format(exc.code, body[:200])]
    except Exception as exc:
        return ["Gemini API failed: {}".format(exc)]

    parts = (((raw.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    if not parts:
        return ["Gemini API returned no text candidates"]
    print("gemini: ok {}".format(model))
    return []


def _telegram_api(token: str, method: str, params=None):
    query = urllib.parse.urlencode(params or {})
    url = "https://api.telegram.org/bot{}/{}".format(token, method)
    if query:
        url = "{}?{}".format(url, query)
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"ok": False, "error_code": exc.code, "description": body}
    except Exception as exc:
        return {"ok": False, "description": str(exc)}


if __name__ == "__main__":
    sys.exit(main())
