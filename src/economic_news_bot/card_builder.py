"""Light, finance-app styled card renderer.

All drawing is done in a logical 1080x1080 space and supersampled (SS=2) for
crisp text and rounded shapes. The geometry constants here are the single
source of truth; ``layout_problems`` measures against the exact same wrapping so
the quality gate never disagrees with what is actually drawn.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .models import BuiltCardSet, ProcessedNews

# --- palette ---------------------------------------------------------------
BG = "#FFFFFF"
INK = "#0F172A"        # slate-900
SUBINK = "#475569"     # slate-600
MUTED = "#94A3B8"      # slate-400
HAIRLINE = "#E6EBF3"
SURFACE = "#F4F7FC"

BLUE = "#2563EB"
BLUE_SOFT = "#EAF1FF"
TEAL = "#0E9F8E"
TEAL_SOFT = "#E4F5F2"
AMBER = "#E08600"
AMBER_SOFT = "#FCEFD9"

# --- geometry (logical px) -------------------------------------------------
CARD_SIZE: Tuple[int, int] = (1080, 1080)
SS = 2                 # supersampling factor
M = 84                 # outer margin
CONTENT_W = CARD_SIZE[0] - 2 * M
FOOTER_Y = 1006

# cover
HEAD_SIZE, HEAD_LEAD, HEAD_MAX_LINES = 78, 92, 2
COVER_SENT_SIZE, COVER_SENT_LEAD, COVER_SENT_MAX_LINES = 40, 58, 3

# numbered card body
BODY_SIZE, BODY_LEAD, BODY_MAX_LINES = 33, 49, 4
BADGE = 56
BODY_X = M + BADGE + 30
BODY_W = (CARD_SIZE[0] - M) - BODY_X

_PIL_ERROR: Optional[str] = None
try:  # Pillow is a hard dependency; fail loudly only when actually rendering.
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except ImportError as exc:  # pragma: no cover - exercised only without Pillow
    Image = ImageDraw = ImageFont = None  # type: ignore
    _PIL_ERROR = str(exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_cards(news_items, config: dict, output_dir: str) -> List[BuiltCardSet]:
    _ensure_pil()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    date_label = _today_label(str(config.get("timezone", "Asia/Seoul")))

    built = []
    for item in news_items:
        item_dir = output_path / "rank_{:02d}".format(item.rank)
        item_dir.mkdir(parents=True, exist_ok=True)
        for stale in item_dir.glob("*.png"):
            stale.unlink()
        files = _render_set(item, item_dir, date_label)
        built.append(
            BuiltCardSet(
                rank=item.rank,
                source=item.source,
                url=item.url,
                files=[str(path) for path in files],
                caption=_caption(item),
            )
        )
    return built


def layout_problems(item: ProcessedNews) -> List[str]:
    """Return human-readable reasons the item would clip, measured exactly as drawn."""
    if Image is None:
        return []
    problems = []
    if len(_wrap(item.headline, HEAD_SIZE, True, CONTENT_W)) > HEAD_MAX_LINES:
        problems.append("headline would be clipped.")
    if len(_wrap(_cover_sentence(item), COVER_SENT_SIZE, False, CONTENT_W)) > COVER_SENT_MAX_LINES:
        problems.append("cover sentence would be clipped.")
    for label, sentences in (
        ("summary", _summary_sentences(item)),
        ("points", _point_sentences(item)),
        ("comment", _investor_sentences(item)),
    ):
        for index, sentence in enumerate(sentences, start=1):
            if len(_wrap(sentence, BODY_SIZE, False, BODY_W)) > BODY_MAX_LINES:
                problems.append("{} {} would be clipped.".format(label, index))
    return problems


# ---------------------------------------------------------------------------
# Card set
# ---------------------------------------------------------------------------

def _render_set(item: ProcessedNews, item_dir: Path, date_label: str) -> Sequence[Path]:
    total = 5
    files = [
        _draw_cover(item, item_dir / "01_cover.png", date_label, 1, total),
        _draw_block_card(
            item_dir / "02_summary.png", BLUE, BLUE_SOFT, "쉬운 요약", "핵심을 3문장으로",
            _summary_sentences(item), 2, total,
        ),
        _draw_block_card(
            item_dir / "03_points.png", TEAL, TEAL_SOFT, "핵심 포인트", "무엇을 체크할까요",
            _point_sentences(item), 3, total,
        ),
        _draw_block_card(
            item_dir / "04_investor.png", AMBER, AMBER_SOFT, "투자자 관점", "시장은 이렇게 봅니다",
            _investor_sentences(item), 4, total,
        ),
        _draw_sources(item, item_dir / "05_sources.png", 5, total),
    ]
    return files


def _draw_cover(item: ProcessedNews, path: Path, date_label: str, page: int, total: int) -> Path:
    c = _Canvas(CARD_SIZE, BG)
    c.rect((0, 0, CARD_SIZE[0], 8), BLUE)

    # brand row
    c.ellipse((M, 84, M + 16, 100), BLUE)
    c.text(M + 26, 80, "경제야 뭐했니", 26, True, INK)
    c.text(CARD_SIZE[0] - M, 82, "MORNING BRIEF", 22, True, MUTED, anchor="ra")

    # kicker chip
    _chip(c, M, 250, "오늘의 경제 이슈", BLUE, BLUE_SOFT)

    # headline
    head_lines = _wrap(item.headline, HEAD_SIZE, True, CONTENT_W)[:HEAD_MAX_LINES]
    y = 330
    y = c.lines(M, y, head_lines, HEAD_SIZE, True, INK, HEAD_LEAD)
    c.rrect((M, y + 10, M + 72, y + 20), 5, fill=BLUE)

    # one-sentence summary
    sent_lines = _wrap(_cover_sentence(item), COVER_SENT_SIZE, False, CONTENT_W)[:COVER_SENT_MAX_LINES]
    c.lines(M, y + 56, sent_lines, COVER_SENT_SIZE, False, SUBINK, COVER_SENT_LEAD)

    # footer
    c.line((M, FOOTER_Y - 24, CARD_SIZE[0] - M, FOOTER_Y - 24), HAIRLINE, 2)
    c.text(M, FOOTER_Y, _source_label(item), 24, True, SUBINK)
    c.text(CARD_SIZE[0] - M, FOOTER_Y, date_label, 24, False, MUTED, anchor="ra")
    return c.save(path)


def _draw_block_card(path, accent, accent_soft, tag, title, sentences, page, total) -> Path:
    c = _Canvas(CARD_SIZE, BG)
    c.rect((0, 0, CARD_SIZE[0], 8), accent)
    _header(c, accent, page, total)

    _chip(c, M, 150, tag, accent, accent_soft)
    c.text(M, 214, title, 47, True, INK)
    c.rrect((M, 286, M + 64, 295), 4, fill=accent)

    _blocks(c, sentences, accent, accent_soft, top=336)
    _footer(c, accent, page, total)
    return c.save(path)


def _draw_sources(item: ProcessedNews, path: Path, page: int, total: int) -> Path:
    c = _Canvas(CARD_SIZE, BG)
    c.rect((0, 0, CARD_SIZE[0], 8), BLUE)
    _header(c, BLUE, page, total)

    _chip(c, M, 150, "원문 보기", BLUE, BLUE_SOFT)
    c.text(M, 214, "이 이슈의 출처", 47, True, INK)
    c.rrect((M, 286, M + 64, 295), 4, fill=BLUE)
    c.text(M, 320, "전체 원문 주소는 메시지 캡션에 담겨 있어요.", 26, False, MUTED)

    sources = (item.sources or [])[:4]
    row_h, gap = 118, 22
    block_h = len(sources) * row_h + max(0, len(sources) - 1) * gap
    region_top, region_bottom = 410, 950
    y = region_top + max(0, (region_bottom - region_top - block_h)) // 2
    for index, source in enumerate(sources, start=1):
        c.rrect((M, y, CARD_SIZE[0] - M, y + row_h), 24, fill=SURFACE)
        c.rrect((M + 26, y + 31, M + 26 + 56, y + 31 + 56), 16, fill=BLUE_SOFT)
        c.text(M + 26 + 28, y + 31 + 28, "{}".format(index), 30, True, BLUE, anchor="mm")
        c.text(M + 122, y + 30, source.source or item.source, 34, True, INK)
        c.text(M + 122, y + 72, _domain(source.url), 26, False, MUTED)
        c.text(CARD_SIZE[0] - M - 30, y + row_h / 2, "↗", 38, True, "#C3CCDB", anchor="mm")
        y += row_h + gap

    _page_dots(c, BLUE, page, total)
    return c.save(path)


# ---------------------------------------------------------------------------
# Shared pieces
# ---------------------------------------------------------------------------

def _header(c: "_Canvas", accent: str, page: int, total: int) -> None:
    c.ellipse((M, 84, M + 16, 100), accent)
    c.text(M + 26, 80, "경제야 뭐했니", 26, True, INK)
    c.text(CARD_SIZE[0] - M, 82, "{} / {}".format(page, total), 24, True, MUTED, anchor="ra")


def _footer(c: "_Canvas", accent: str, page: int, total: int) -> None:
    _page_dots(c, accent, page, total)


def _page_dots(c: "_Canvas", accent: str, page: int, total: int) -> None:
    gap = 26
    r = 6
    width = (total - 1) * gap
    start = CARD_SIZE[0] / 2 - width / 2
    cy = FOOTER_Y + 18
    for i in range(total):
        cx = start + i * gap
        if i == page - 1:
            c.rrect((cx - 14, cy - r, cx + 14, cy + r), r, fill=accent)
        else:
            c.ellipse((cx - r, cy - r, cx + r, cy + r), HAIRLINE)


def _chip(c: "_Canvas", x: int, y: int, text: str, accent: str, soft: str) -> None:
    pad = 22
    w = c.text_w(text, 27, True) + pad * 2
    c.rrect((x, y, x + w, y + 48), 24, fill=soft)
    c.text(x + pad, y + 9, text, 27, True, accent)


def _blocks(c: "_Canvas", sentences: List[str], accent: str, accent_soft: str, top: int) -> None:
    wrapped = [_wrap(s, BODY_SIZE, False, BODY_W)[:BODY_MAX_LINES] for s in sentences[:3]]
    counts = [max(1, len(lines)) for lines in wrapped]

    lead, gap = BODY_LEAD, 30
    available = FOOTER_Y - 26 - top
    needed = sum(max(BADGE, n * lead) for n in counts) + gap * (len(counts) - 1)
    if needed > available and needed > 0:  # gracefully tighten rather than clip
        scale = available / needed
        lead = max(42, int(lead * scale))
        gap = max(20, int(gap * scale))

    y = top
    for index, lines in enumerate(wrapped, start=1):
        c.rrect((M, y, M + BADGE, y + BADGE), 16, fill=accent_soft)
        c.text(M + BADGE / 2, y + BADGE / 2, "{}".format(index), 30, True, accent, anchor="mm")
        c.lines(BODY_X, y + 3, lines, BODY_SIZE, False, INK, lead)
        block_h = max(BADGE, len(lines) * lead)
        y += block_h + gap


# ---------------------------------------------------------------------------
# Content selectors
# ---------------------------------------------------------------------------

def _summary_sentences(item: ProcessedNews) -> List[str]:
    return _ensure_three(_lines_or_sentences(item.summary), item.headline)


def _point_sentences(item: ProcessedNews) -> List[str]:
    return _ensure_three([p.strip() for p in item.points if p and p.strip()], item.headline)


def _investor_sentences(item: ProcessedNews) -> List[str]:
    fallback = "투자 판단 전 원문 수치와 시장 반응을 함께 확인해야 합니다."
    return _ensure_three(_lines_or_sentences(item.comment), fallback)


def _cover_sentence(item: ProcessedNews) -> str:
    if item.one_sentence:
        return _finish(item.one_sentence)
    candidates = _lines_or_sentences(item.summary)
    return _finish(candidates[0]) if candidates else _finish(item.headline)


def _source_label(item: ProcessedNews) -> str:
    names = []
    for source in item.sources or []:
        if source.source and source.source not in names:
            names.append(source.source)
    if len(names) >= 2:
        return "{} 외 {}곳".format(names[0], len(names) - 1)
    return names[0] if names else item.source


def _caption(item: ProcessedNews) -> str:
    # Telegram media-group captions are capped at 1024 chars; stay safely under.
    budget = 1000
    sources = item.sources or []
    if not sources:
        return "출처: {}\n{}".format(item.source, item.url)[:budget]
    names = []
    for source in sources:
        if source.source and source.source not in names:
            names.append(source.source)
    lines = ["📰 {}".format(item.headline), "", "출처: {}".format(", ".join(names))]
    used = sum(len(line) + 1 for line in lines)
    for index, source in enumerate(sources, start=1):
        if not source.url:
            continue
        entry = "원문 {}: {}".format(index, source.url)
        if used + len(entry) + 1 > budget:
            break
        lines.append(entry)
        used += len(entry) + 1
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _lines_or_sentences(value: str) -> List[str]:
    lines = [line.strip() for line in (value or "").splitlines() if line.strip()]
    if len(lines) >= 2:
        return [_finish(line) for line in lines]
    value = re.sub(r"\s+", " ", value or "").strip()
    if not value:
        return []
    parts = re.split(r"(?<=[.!?])\s+", value)
    return [_finish(part.strip()) for part in parts if part.strip()]


def _ensure_three(values: List[str], fallback: str) -> List[str]:
    output = [_finish(v) for v in values if v and v.strip()]
    fallback = _finish(fallback)
    while len(output) < 3:
        output.append(fallback)
    return output[:3]


def _finish(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if not value:
        return ""
    return value if value[-1] in ".!?。？！" else value + "."


def _domain(url: str) -> str:
    match = re.search(r"https?://([^/]+)", url or "")
    host = match.group(1) if match else (url or "")
    return host[4:] if host.startswith("www.") else host


def _today_label(tz_name: str) -> str:
    try:
        from zoneinfo import ZoneInfo  # type: ignore

        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now = datetime.now()
    weekday = "월화수목금토일"[now.weekday()]
    return "{}년 {}월 {}일 ({})".format(now.year, now.month, now.day, weekday)


# ---------------------------------------------------------------------------
# Rendering primitives
# ---------------------------------------------------------------------------

_FONT_CACHE: dict = {}
_MEASURE = None


def _ensure_pil() -> None:
    if Image is None:
        raise RuntimeError("Pillow is required to render cards ({}). Install requirements.txt.".format(_PIL_ERROR))


def _font_path(bold: bool) -> str:
    candidates = [
        Path("assets") / "fonts" / ("Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto") / ("NotoSansCJK-Bold.ttc" if bold else "NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/nanum") / ("NanumGothicBold.ttf" if bold else "NanumGothic.ttf"),
        Path("C:/Windows/Fonts") / ("malgunbd.ttf" if bold else "malgun.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def _font(size: int, bold: bool):
    key = (size, bold)
    cached = _FONT_CACHE.get(key)
    if cached is None:
        path = _font_path(bold)
        if path:
            cached = ImageFont.truetype(path, size * SS)
        else:  # pragma: no cover - last resort, Korean will not render well
            cached = ImageFont.load_default()
        _FONT_CACHE[key] = cached
    return cached


def _measure_draw():
    global _MEASURE
    if _MEASURE is None:
        _MEASURE = ImageDraw.Draw(Image.new("L", (8, 8)))
    return _MEASURE


def _text_width(text: str, size: int, bold: bool) -> float:
    return _measure_draw().textlength(text, font=_font(size, bold)) / SS


def _wrap(text: str, size: int, bold: bool, max_w: float) -> List[str]:
    words = re.sub(r"\s+", " ", text or "").strip().split(" ")
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if _text_width(candidate, size, bold) <= max_w:
            current = candidate
            continue
        if current:
            lines.append(current)
        if _text_width(word, size, bold) <= max_w:
            current = word
        else:
            pieces = _split_token(word, size, bold, max_w)
            lines.extend(pieces[:-1])
            current = pieces[-1] if pieces else ""
    if current:
        lines.append(current)
    return lines


def _split_token(word: str, size: int, bold: bool, max_w: float) -> List[str]:
    pieces, current = [], ""
    for char in word:
        if _text_width(current + char, size, bold) <= max_w:
            current += char
        else:
            if current:
                pieces.append(current)
            current = char
    if current:
        pieces.append(current)
    return pieces


class _Canvas:
    def __init__(self, size: Tuple[int, int], bg: str):
        self.w, self.h = size
        self.img = Image.new("RGB", (self.w * SS, self.h * SS), bg)
        self.d = ImageDraw.Draw(self.img)

    def text(self, x, y, s, size, bold, fill, anchor=None):
        self.d.text((x * SS, y * SS), s, font=_font(size, bold), fill=fill, anchor=anchor)

    def text_w(self, s, size, bold) -> float:
        return _text_width(s, size, bold)

    def lines(self, x, y, lines, size, bold, fill, leading) -> float:
        for line in lines:
            self.text(x, y, line, size, bold, fill)
            y += leading
        return y

    def rect(self, box, fill):
        self.d.rectangle([v * SS for v in box], fill=fill)

    def rrect(self, box, radius, fill=None, outline=None, width=1):
        self.d.rounded_rectangle([v * SS for v in box], radius=radius * SS, fill=fill, outline=outline, width=max(1, width * SS))

    def line(self, box, fill, width):
        self.d.line([v * SS for v in box], fill=fill, width=max(1, width * SS))

    def ellipse(self, box, fill):
        self.d.ellipse([v * SS for v in box], fill=fill)

    def save(self, path: Path) -> Path:
        self.img.resize((self.w, self.h), Image.LANCZOS).save(path)
        return path
