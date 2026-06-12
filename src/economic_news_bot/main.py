import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .ai_processor import process_articles
from .card_builder import build_cards
from .config import load_config, read_env_file
from .dispatcher import dispatch_card_sets, notify_admin
from .models import ArticleCandidate
from .quality import validate_processed_news
from .rss_fetcher import fetch_candidates


class _GeminiUnavailable(RuntimeError):
    """Raised when only fallback cards exist, so publishing is skipped and retried later."""


def main() -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(description="Daily economic card news bot")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sample", action="store_true", help="Use samples/sample_articles.json instead of live RSS.")
    parser.add_argument("--fallback-ai", action="store_true", help="Do not call Gemini even when GEMINI_API_KEY exists.")
    parser.add_argument("--limit", type=int, default=0, help="Limit processed news count for smoke tests.")
    args = parser.parse_args()

    read_env_file(args.env)
    config = load_config(args.config)
    base_dir = Path(config.get("_config_dir", "."))
    output_dir = base_dir / str(config.get("output_dir", "output"))

    try:
        candidates = _load_sample(base_dir) if args.sample else fetch_candidates(config)
        if not candidates:
            print("[WARN] No live RSS candidates found. Falling back to sample articles.")
            candidates = _load_sample(base_dir)

        runtime_config = dict(config)
        if args.limit:
            runtime_config["news_count"] = args.limit
        processed = process_articles(candidates, runtime_config, force_fallback=args.fallback_ai)
        if args.limit:
            processed = processed[: args.limit]
        if len(processed) < int(config.get("news_count", 6)):
            print("[WARN] Only {} processed items were produced.".format(len(processed)))
        if not args.dry_run and _looks_like_fallback(processed) and not config.get("allow_fallback_publish", False):
            raise _GeminiUnavailable(
                "Gemini 처리 실패로 fallback 카드가 생성되어 실제 발송을 중단합니다. 다음 예약 실행이 자동으로 재시도합니다."
            )

        validate_processed_news(processed, config)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "candidates.json").write_text(
            json.dumps([_candidate_to_dict(item) for item in candidates], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "processed_news.json").write_text(
            json.dumps([asdict(item) for item in processed], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        card_sets = build_cards(processed, config, str(output_dir))
        dispatch_card_sets(card_sets, dry_run=args.dry_run, delay_seconds=float(config.get("telegram_album_delay_seconds", 10)))
        notify_admin("경제야 뭐했니 발송 완료 - {}건".format(len(card_sets)) if not args.dry_run else "Dry-run 완료 - {}건".format(len(card_sets)))
        print("[DONE] Built {} news card sets in {}".format(len(card_sets), output_dir))
        return 0
    except _GeminiUnavailable as exc:
        # Expected, self-healing: a later scheduled tick retries. Don't spam admin.
        print("[INFO] {}".format(exc))
        raise
    except Exception as exc:
        notify_admin("경제야 뭐했니 실행 실패: {}".format(exc))
        raise


def _force_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


def _load_sample(base_dir: Path):
    sample_path = base_dir / "samples" / "sample_articles.json"
    with sample_path.open("r", encoding="utf-8") as handle:
        raw_items = json.load(handle)
    return [
        ArticleCandidate(
            title=item["title"],
            url=item["url"],
            source=item["source"],
            summary=item.get("summary", ""),
        )
        for item in raw_items
    ]


def _candidate_to_dict(item: ArticleCandidate):
    return {
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "summary": item.summary,
    }


def _looks_like_fallback(processed) -> bool:
    fallback_markers = ("AI 키 없이 만든 점검용 요약", "점검용 요약이므로 투자 판단의 근거로")
    for item in processed:
        text = "{}\n{}\n{}".format(item.summary, item.comment, "\n".join(item.points))
        if any(marker in text for marker in fallback_markers):
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
