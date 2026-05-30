import argparse
import sys

from .config import load_config
from .rss_fetcher import _fetch_one_source


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect configured RSS sources.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--include-disabled", action="store_true")
    parser.add_argument("--hours", type=int, default=72)
    args = parser.parse_args()

    config = load_config(args.config)
    sources = config.get("rss_sources", [])
    if not args.include_disabled:
        sources = [source for source in sources if source.get("enabled", True)]

    failures = 0
    for source in sources:
        name = source.get("name", "unknown")
        try:
            items = _fetch_one_source(source, hours=args.hours)
            sample = items[0].title if items else "no recent items"
            print("[OK] {}: {} item(s) - {}".format(name, len(items), sample[:80]))
        except Exception as exc:
            failures += 1
            print("[FAIL] {}: {}".format(name, exc))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
