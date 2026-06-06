import re
from typing import Iterable, List, Optional

from .models import ProcessedNews


TRUNCATION_MARKERS = ("...", "\u2026", "\u22ef")
TERMINAL_PUNCTUATION = (".", "!", "?")
BAD_ENDINGS = (",", ";", ":", "-", "\u2013", "\u2014")


def validate_processed_news(news_items: Iterable[ProcessedNews], config: Optional[dict] = None) -> None:
    items = list(news_items)
    if not items:
        raise ValueError("quality check failed: no processed news items.")

    for item in items:
        _validate_item_text(item)

    if config is not None and config.get("validate_card_layout", True):
        _validate_card_layout(items)


def _validate_item_text(item: ProcessedNews) -> None:
    summary = _non_empty_lines(item.summary)
    comment = _non_empty_lines(item.comment)
    points = [point.strip() for point in item.points if point and point.strip()]

    if len(summary) != 3:
        raise ValueError("quality check failed: rank {} summary must have 3 sentences.".format(item.rank))
    if len(points) != 3:
        raise ValueError("quality check failed: rank {} points must have 3 sentences.".format(item.rank))
    if len(comment) != 3:
        raise ValueError("quality check failed: rank {} comment must have 3 sentences.".format(item.rank))

    for label, sentence in _iter_body_sentences(item, summary, points, comment):
        _validate_complete_sentence(item.rank, label, sentence)

    if item.one_sentence:
        _validate_complete_sentence(item.rank, "cover", item.one_sentence, min_chars=20, max_chars=130)


def _iter_body_sentences(item: ProcessedNews, summary: List[str], points: List[str], comment: List[str]):
    for index, sentence in enumerate(summary, start=1):
        yield "summary {}".format(index), sentence
    for index, sentence in enumerate(points, start=1):
        yield "point {}".format(index), sentence
    for index, sentence in enumerate(comment, start=1):
        yield "comment {}".format(index), sentence


def _validate_complete_sentence(rank: int, label: str, sentence: str, min_chars: int = 45, max_chars: int = 145) -> None:
    text = re.sub(r"\s+", " ", sentence or "").strip()
    if len(text) < min_chars:
        raise ValueError("quality check failed: rank {} {} is too short.".format(rank, label))
    if len(text) > max_chars:
        raise ValueError("quality check failed: rank {} {} is too long for card layout.".format(rank, label))
    if any(marker in text for marker in TRUNCATION_MARKERS):
        raise ValueError("quality check failed: rank {} {} looks truncated.".format(rank, label))
    if text.endswith(BAD_ENDINGS):
        raise ValueError("quality check failed: rank {} {} ends incompletely.".format(rank, label))
    if not text.endswith(TERMINAL_PUNCTUATION):
        raise ValueError("quality check failed: rank {} {} must end with sentence punctuation.".format(rank, label))


def _validate_card_layout(items: List[ProcessedNews]) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except ImportError:
        return

    from .card_builder import (
        _cover_sentence,
        _investor_sentences,
        _load_font,
        _point_sentences,
        _summary_sentences,
        _wrap_to_width,
    )

    image = Image.new("RGB", (1080, 1080), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    fonts = {
        "display": _load_font(74, ImageFont, bold=True),
        "cover_summary": _load_font(46, ImageFont, bold=True),
        "body": _load_font(26, ImageFont),
    }

    for item in items:
        if len(_wrap_to_width(draw, item.headline, fonts["display"], 900, max_lines=99)) > 2:
            raise ValueError("quality check failed: rank {} headline would be clipped.".format(item.rank))
        if len(_wrap_to_width(draw, _cover_sentence(item), fonts["cover_summary"], 900, max_lines=99)) > 3:
            raise ValueError("quality check failed: rank {} cover sentence would be clipped.".format(item.rank))
        for section, sentences in (
            ("summary", _summary_sentences(item)),
            ("points", _point_sentences(item)),
            ("comment", _investor_sentences(item)),
        ):
            for index, sentence in enumerate(sentences, start=1):
                lines = _wrap_to_width(draw, sentence, fonts["body"], 590, max_lines=99)
                if len(lines) > 4:
                    raise ValueError(
                        "quality check failed: rank {} {} {} would be clipped.".format(item.rank, section, index)
                    )


def _non_empty_lines(value: str) -> List[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]
