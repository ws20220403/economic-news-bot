import re
from typing import Iterable, List, Optional

from .models import ProcessedNews

# Content length targets shared with the AI prompt. The pixel-level layout check
# below is the real gate against clipping; these keep the text in a sane band.
HEADLINE_MAX_CHARS = 34
COVER_MAX_CHARS = 62
BODY_MIN_CHARS = 45
BODY_MAX_CHARS = 90

SENTENCES_PER_BLOCK = 3
TRUNCATION_MARKERS = ("...", "…", "⋯")
TERMINAL_PUNCTUATION = (".", "!", "?")
BAD_ENDINGS = (",", ";", ":", "-", "–", "—")


def validate_processed_news(news_items: Iterable[ProcessedNews], config: Optional[dict] = None) -> None:
    items = list(news_items)
    if not items:
        raise ValueError("quality check failed: no processed news items.")

    for item in items:
        _validate_item_text(item)

    if config is None or config.get("validate_card_layout", True):
        _validate_card_layout(items)


def _validate_item_text(item: ProcessedNews) -> None:
    if not item.headline.strip():
        raise ValueError("quality check failed: rank {} headline is empty.".format(item.rank))
    if not item.sources:
        raise ValueError("quality check failed: rank {} has no source.".format(item.rank))

    summary = _non_empty_lines(item.summary)
    comment = _non_empty_lines(item.comment)
    points = [point.strip() for point in item.points if point and point.strip()]

    for label, block in (("summary", summary), ("points", points), ("comment", comment)):
        if len(block) != SENTENCES_PER_BLOCK:
            raise ValueError(
                "quality check failed: rank {} {} must have {} sentences.".format(item.rank, label, SENTENCES_PER_BLOCK)
            )

    for label, sentence in _iter_body_sentences(summary, points, comment):
        _validate_complete_sentence(item.rank, label, sentence, min_chars=BODY_MIN_CHARS - 15, max_chars=BODY_MAX_CHARS + 18)

    if item.one_sentence:
        _validate_complete_sentence(item.rank, "cover", item.one_sentence, min_chars=18, max_chars=COVER_MAX_CHARS + 12)


def _iter_body_sentences(summary: List[str], points: List[str], comment: List[str]):
    for index, sentence in enumerate(summary, start=1):
        yield "summary {}".format(index), sentence
    for index, sentence in enumerate(points, start=1):
        yield "point {}".format(index), sentence
    for index, sentence in enumerate(comment, start=1):
        yield "comment {}".format(index), sentence


def _validate_complete_sentence(rank: int, label: str, sentence: str, min_chars: int, max_chars: int) -> None:
    text = re.sub(r"\s+", " ", sentence or "").strip()
    if len(text) < min_chars:
        raise ValueError("quality check failed: rank {} {} is too short.".format(rank, label))
    if len(text) > max_chars:
        raise ValueError("quality check failed: rank {} {} is too long.".format(rank, label))
    if any(marker in text for marker in TRUNCATION_MARKERS):
        raise ValueError("quality check failed: rank {} {} looks truncated.".format(rank, label))
    if text.endswith(BAD_ENDINGS):
        raise ValueError("quality check failed: rank {} {} ends incompletely.".format(rank, label))
    if not text.endswith(TERMINAL_PUNCTUATION):
        raise ValueError("quality check failed: rank {} {} must end with sentence punctuation.".format(rank, label))


def _validate_card_layout(items: List[ProcessedNews]) -> None:
    try:
        from .card_builder import layout_problems
    except Exception:
        return

    for item in items:
        problems = layout_problems(item)
        if problems:
            raise ValueError("quality check failed: rank {} {}".format(item.rank, problems[0]))


def _non_empty_lines(value: str) -> List[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]
