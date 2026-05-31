import html
import re
import textwrap
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from .models import BuiltCardSet, ProcessedNews


BLUE = "#194BFF"
CYAN = "#00A9C8"
ORANGE = "#FF9D00"
INK = "#111111"
MUTED = "#5F6673"
PAPER = "#FFFFFF"
LINE = "#D7DFEE"


def build_cards(news_items: Iterable[ProcessedNews], config: dict, output_dir: str) -> List[BuiltCardSet]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    size = tuple(config.get("card_size", [1080, 1080]))
    built = []

    for item in news_items:
        item_dir = output_path / "rank_{:02d}".format(item.rank)
        item_dir.mkdir(parents=True, exist_ok=True)
        for stale in list(item_dir.glob("*.png")) + list(item_dir.glob("*.svg")):
            stale.unlink()
        files = _build_one_set(item, item_dir, size)
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


def wrap_text(value: str, width: int, max_lines: int) -> List[str]:
    lines = []
    for paragraph in (value or "").splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        lines.extend(textwrap.wrap(paragraph, width=width, break_long_words=True, replace_whitespace=False))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .…") + "…"
    return lines


def _build_one_set(item: ProcessedNews, item_dir: Path, size: Tuple[int, int]) -> Sequence[Path]:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except ImportError:
        return _build_svg_set(item, item_dir, size)

    fonts = {
        "display": _load_font(74, ImageFont, bold=True),
        "h1": _load_font(50, ImageFont, bold=True),
        "h2": _load_font(38, ImageFont, bold=True),
        "body": _load_font(26, ImageFont),
        "body_bold": _load_font(26, ImageFont, bold=True),
        "small": _load_font(24, ImageFont),
        "tiny": _load_font(19, ImageFont),
        "cover_summary": _load_font(46, ImageFont, bold=True),
    }

    files = []
    files.append(_draw_cover(item, item_dir / "01_cover.png", size, Image, ImageDraw, fonts))
    files.append(
        _draw_numbered_card(
            item_dir / "02_summary.png",
            size,
            Image,
            ImageDraw,
            fonts,
            section="쉬운 요약",
            title="3문장으로 보면",
            sentences=_summary_sentences(item),
            accent=BLUE,
        )
    )
    files.append(
        _draw_numbered_card(
            item_dir / "03_points.png",
            size,
            Image,
            ImageDraw,
            fonts,
            section="핵심 포인트",
            title="무엇을 체크해야 할까요?",
            sentences=_point_sentences(item),
            accent=CYAN,
        )
    )
    files.append(
        _draw_numbered_card(
            item_dir / "04_investor.png",
            size,
            Image,
            ImageDraw,
            fonts,
            section="투자자 관점",
            title="시장에서는 이렇게 봅니다",
            sentences=_investor_sentences(item),
            accent=ORANGE,
        )
    )
    files.append(_draw_source_card(item, item_dir / "05_sources.png", size, Image, ImageDraw, fonts))
    return files


def _load_font(size: int, image_font, bold: bool = False):
    pretendard = Path("assets") / "font_candidates" / "Pretendard" / "public" / "static" / "alternative"
    candidates = [
        Path("assets") / "fonts" / ("Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"),
        pretendard / ("Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"),
        Path("assets") / "fonts" / ("NotoSansKR-Bold.otf" if bold else "NotoSansKR-Regular.otf"),
        Path("C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return image_font.truetype(str(candidate), size)
            except Exception:
                pass
    return image_font.load_default()


def _draw_cover(item, path, size, image_mod, draw_mod, fonts):
    image = image_mod.new("RGB", size, PAPER)
    draw = draw_mod.Draw(image)
    draw.rectangle([0, 0, size[0], 38], fill=BLUE)
    draw.text((74, 82), "경제야 뭐했니", fill=MUTED, font=fonts["small"])
    draw.text((74, 118), "ECONOMY EXPLAINER", fill=BLUE, font=fonts["h2"])

    headline_lines = _wrap_to_width(draw, item.headline, fonts["display"], 900, max_lines=2)
    _draw_lines(draw, headline_lines, 74, 220, fonts["display"], INK, 86)
    draw.rectangle([74, 520, 780, 544], fill=BLUE)

    one_sentence = _cover_sentence(item)
    summary_lines = _wrap_to_width(draw, one_sentence, fonts["cover_summary"], 900, max_lines=3)
    _draw_lines(draw, summary_lines, 74, 610, fonts["cover_summary"], INK, 54)
    draw.text((74, 930), _source_label(item), fill=MUTED, font=fonts["small"])

    image.save(path)
    return path


def _draw_numbered_card(path, size, image_mod, draw_mod, fonts, section, title, sentences, accent):
    image = image_mod.new("RGB", size, PAPER)
    draw = draw_mod.Draw(image)
    draw.rectangle([0, 0, size[0], 38], fill=accent)
    draw.text((74, 82), "경제야 뭐했니", fill=MUTED, font=fonts["small"])
    draw.text((74, 118), section, fill=accent, font=fonts["h2"])
    _big_title(draw, title, 74, 190, fonts, accent)
    _numbered_paragraphs(draw, sentences[:3], 74, 335, fonts, accent)
    image.save(path)
    return path


def _draw_source_card(item, path, size, image_mod, draw_mod, fonts):
    source_path = Path("assets") / "images" / "ai_source_card_background.png"
    if not source_path.exists():
        source_path = Path("output") / "design_drafts" / "ai_source_card_background.png"
    if source_path.exists():
        image = image_mod.open(source_path).convert("RGB").resize(size)
        overlay = image_mod.new("RGBA", size, (255, 255, 255, 120))
        image = image_mod.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    else:
        image = _fallback_source_background(size, image_mod, draw_mod)

    draw = draw_mod.Draw(image)
    draw.rectangle([0, 0, size[0], 38], fill=BLUE)
    button_text = "원문 보기"
    bbox = draw.textbbox((0, 0), button_text, font=fonts["h2"])
    button_width = bbox[2] - bbox[0] + 110
    left = int((size[0] - button_width) / 2)
    _round(draw, [left, 245, left + button_width, 335], 45, BLUE)
    _center(draw, button_text, size[0] / 2, 268, fonts["h2"], PAPER)
    image.save(path)
    return path


def _fallback_source_background(size, image_mod, draw_mod):
    image = image_mod.new("RGB", size, PAPER)
    draw = draw_mod.Draw(image)
    draw.rectangle([400, 545, 700, 920], fill="#F8FAFD", outline=LINE, width=3)
    draw.polygon([(635, 545), (700, 610), (635, 610)], fill="#7D98FF")
    draw.ellipse([585, 660, 805, 880], outline="#7B8798", width=22)
    draw.line([765, 840, 875, 950], fill="#7B8798", width=28)
    draw.line([74, 940, 1006, 940], fill=LINE, width=3)
    return image


def _numbered_paragraphs(draw, paragraphs, x, y, fonts, accent):
    for idx, paragraph in enumerate(paragraphs, start=1):
        number_text = "0{}".format(idx)
        text_x = x + 76
        rule_right = text_x + 590
        lines = _wrap_to_width(draw, paragraph, fonts["body"], rule_right - text_x, max_lines=4)
        draw.text((x, y), number_text, fill=accent, font=fonts["h1"])
        _draw_lines(draw, lines, text_x, y + 7, fonts["body"], INK, 37)
        line_y = y + 26 + len(lines) * 37
        draw.line([text_x, line_y, rule_right, line_y], fill=LINE, width=2)
        y += max(178, len(lines) * 37 + 94)


def _big_title(draw, text, x, y, fonts, accent):
    draw.text((x, y), text, fill=INK, font=fonts["h1"])
    title_width = _text_width(draw, text, fonts["h1"])
    draw.rectangle([x, y + 64, x + title_width, y + 74], fill=accent)


def _summary_sentences(item: ProcessedNews) -> List[str]:
    return _ensure_three(_split_lines_or_sentences(item.summary), item.headline)


def _point_sentences(item: ProcessedNews) -> List[str]:
    return _ensure_three([point.strip() for point in item.points if point and point.strip()], item.headline)


def _investor_sentences(item: ProcessedNews) -> List[str]:
    fallback = "투자 판단 전 원문 수치와 시장 반응을 함께 확인해야 합니다."
    return _ensure_three(_split_lines_or_sentences(item.comment), fallback)


def _cover_sentence(item: ProcessedNews) -> str:
    if item.one_sentence:
        return _finish_sentence(item.one_sentence)
    candidates = _split_lines_or_sentences(item.summary)
    if candidates:
        return _finish_sentence(candidates[0])
    return _finish_sentence(item.headline)


def _source_label(item: ProcessedNews) -> str:
    sources = item.sources or []
    names = []
    for source in sources:
        if source.source and source.source not in names:
            names.append(source.source)
    if len(names) >= 2:
        return "{} 외 {}곳".format(names[0], len(names) - 1)
    return item.source


def _caption(item: ProcessedNews) -> str:
    sources = item.sources or []
    if not sources:
        return "출처: {}\n{}".format(item.source, item.url)
    source_names = []
    for source in sources:
        if source.source and source.source not in source_names:
            source_names.append(source.source)
    lines = ["출처: {}".format(", ".join(source_names))]
    for index, source in enumerate(sources, start=1):
        if source.url:
            lines.append("원문 {}: {}".format(index, source.url))
    return "\n".join(lines)


def _split_lines_or_sentences(value: str) -> List[str]:
    value = re.sub(r"\s+", " ", value or "").strip()
    if not value:
        return []
    lines = [line.strip() for line in (value or "").splitlines() if line.strip()]
    if len(lines) >= 2:
        return [_finish_sentence(line) for line in lines]
    parts = re.split(r"(?<=[.!?。？！다요임음됨함])\s+", value)
    return [_finish_sentence(part.strip()) for part in parts if part.strip()]


def _ensure_three(values: List[str], fallback: str) -> List[str]:
    output = [_finish_sentence(value) for value in values if value and value.strip()]
    fallback = _finish_sentence(fallback)
    while len(output) < 3:
        output.append(fallback)
    return output[:3]


def _finish_sentence(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if not value:
        return ""
    if value[-1] in ".!?。？！":
        return value
    return value + "."


def _wrap_to_width(draw, text, font, max_width, max_lines):
    words = (text or "").split(" ")
    lines = []
    current = ""

    for word in words:
        candidate = word if not current else current + " " + word
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if _text_width(draw, word, font) <= max_width:
            current = word
        else:
            pieces = _split_long_word(draw, word, font, max_width)
            lines.extend(pieces[:-1])
            current = pieces[-1] if pieces else ""

    if current:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .…") + "…"
    return lines


def _split_long_word(draw, word, font, max_width):
    pieces = []
    current = ""
    for char in word:
        candidate = current + char
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            if current:
                pieces.append(current)
            current = char
    if current:
        pieces.append(current)
    return pieces


def _text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _draw_lines(draw, lines, x, y, font, fill, step):
    for line in lines:
        draw.text((x, y), line, fill=fill, font=font)
        y += step


def _center(draw, text, center_x, y, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((center_x - (bbox[2] - bbox[0]) / 2, y), text, fill=fill, font=font)


def _round(draw, box, radius, fill, outline=None):
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline)
    else:
        draw.rectangle(box, fill=fill, outline=outline)


def _build_svg_set(item: ProcessedNews, item_dir: Path, size: Tuple[int, int]) -> Sequence[Path]:
    specs = [
        ("01_cover.svg", BLUE, "경제야 뭐했니", item.headline),
        ("02_summary.svg", BLUE, "3문장으로 보면", "\n".join(_summary_sentences(item))),
        ("03_points.svg", CYAN, "무엇을 체크해야 할까요?", "\n".join(_point_sentences(item))),
        ("04_investor.svg", ORANGE, "시장에서는 이렇게 봅니다", "\n".join(_investor_sentences(item))),
        ("05_sources.svg", BLUE, "원문 보기", item.source),
    ]
    files = []
    for filename, accent, label, body in specs:
        path = item_dir / filename
        lines = wrap_text(body, 30, 9)
        text_nodes = []
        for idx, line in enumerate(lines):
            text_nodes.append('<text x="90" y="{}" class="body">{}</text>'.format(260 + idx * 58, html.escape(line)))
        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
.label {{ font: 700 42px sans-serif; fill: {accent}; }}
.body {{ font: 400 38px sans-serif; fill: #111111; }}
</style>
<rect width="100%" height="100%" fill="#FFFFFF"/>
<rect width="100%" height="38" fill="{accent}"/>
<text x="74" y="140" class="label">{label}</text>
{body}
</svg>""".format(
            w=size[0],
            h=size[1],
            accent=accent,
            label=html.escape(label),
            body="\n".join(text_nodes),
        )
        path.write_text(svg, encoding="utf-8")
        files.append(path)
    return files
