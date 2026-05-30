from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BLUE = "#194BFF"
NAVY = "#10213F"
INK = "#111111"
MUTED = "#5F6673"
PAPER = "#FFFFFF"
BG = "#EEF3FF"
LINE = "#D7DFEE"
SOFT = "#F5F7FB"
CYAN = "#00A9C8"
ORANGE = "#FF9D00"
PURPLE = "#6F5BFF"


NEWS = {
    "headline": "자영업자 빚 부담 심화,\n연체 두 배 증가",
    "kicker": "오늘의 경제 이슈",
    "source": "매일경제 경제 외",
    "one_sentence": "자영업자 대출 연체가 빠르게 늘며 내수와 금융권 모두의 부담 요인으로 떠오르고 있습니다.",
    "summary": [
        "90일 이상 대출을 갚지 못한 자영업자가 늘며, 개인사업자의 빚 부담이 빠르게 커지고 있습니다.",
        "연체 규모는 2년 만에 두 배로 불었고, 금융채무 불이행자는 94만 명을 넘었습니다.",
        "소비 위축과 금융권 부실 부담으로 이어질 수 있어, 내수 경기의 약한 고리로 봐야 합니다.",
    ],
    "points": [
        "연체 증가는 개인 문제가 아니라 자영업 경기 둔화를 보여주는 신호일 수 있습니다.",
        "은행과 카드사의 부실 위험이 커지면 대출 심사가 더 보수적으로 바뀔 수 있습니다.",
        "정부 지원책과 금리 흐름이 연체 부담을 얼마나 줄일지가 다음 관전 포인트입니다.",
    ],
    "opinion": [
        "유통·외식·카드 업종은 자영업자의 현금흐름 악화가 소비 둔화로 번지는지 봐야 합니다.",
        "금융주는 연체율 추세와 충당금 부담이 실적에 얼마나 반영되는지 확인해야 합니다.",
        "금리 인하 기대는 부담 완화 요인이지만, 경기 둔화가 크면 긍정 효과는 제한될 수 있습니다.",
    ],
}


def main() -> int:
    out_dir = Path("output") / "design_drafts"
    out_dir.mkdir(parents=True, exist_ok=True)

    fonts = {
        "display": _font(74, bold=True),
        "title": _font(62, bold=True),
        "h1": _font(50, bold=True),
        "h2": _font(38, bold=True),
        "body": _font(26),
        "body_bold": _font(26, bold=True),
        "small": _font(24),
        "tiny": _font(19),
    }

    styles = [
        ("F_editorial_blue", draw_editorial_blue),
        ("F_checked_v2", draw_editorial_blue),
        ("G_market_brief", draw_market_brief),
        ("H_clean_magazine", draw_clean_magazine),
        ("I_data_card", draw_data_card),
    ]

    for name, drawer in styles:
        drawer(out_dir, name, fonts)

    draw_font_preview(out_dir)
    print("Wrote {} refined design style(s) to {}".format(len(styles), out_dir.resolve()))
    return 0


def draw_editorial_blue(out_dir, name, f):
    def shell(title, accent=BLUE):
        img = Image.new("RGB", (1080, 1080), PAPER)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 1080, 38], fill=accent)
        d.text((74, 82), "경제야 뭐했니", fill=MUTED, font=f["small"])
        d.text((74, 118), title, fill=accent, font=f["h2"])
        return img, d

    img, d = shell("ECONOMY EXPLAINER")
    d.text((74, 220), NEWS["headline"], fill=INK, font=f["display"], spacing=12)
    d.rectangle([74, 520, 780, 544], fill=BLUE)
    cover_summary_font = _font(46, bold=True)
    _draw_lines(d, _wrap_to_width(d, NEWS["one_sentence"], cover_summary_font, 900, max_lines=3), 74, 610, cover_summary_font, INK, 54)
    d.text((74, 930), NEWS["source"], fill=MUTED, font=f["small"])
    _save(img, out_dir, name, "01_cover")

    img, d = shell("쉬운 요약", BLUE)
    _big_title(d, "3문장으로 보면", 74, 190, f, BLUE)
    _numbered_paragraphs(d, NEWS["summary"], 74, 335, f, style="line", accent=BLUE)
    _save(img, out_dir, name, "02_summary")

    img, d = shell("핵심 포인트", CYAN)
    _big_title(d, "무엇을 체크해야 할까요?", 74, 190, f, CYAN)
    _numbered_paragraphs(d, NEWS["points"], 74, 335, f, style="line", accent=CYAN)
    _save(img, out_dir, name, "03_points")

    img, d = shell("투자자 관점", ORANGE)
    _big_title(d, "시장에서는 이렇게 봅니다", 74, 190, f, ORANGE)
    _numbered_paragraphs(d, NEWS["opinion"], 74, 335, f, style="line", accent=ORANGE)
    _save(img, out_dir, name, "04_investor")

    img, d = _source_background(f)
    _save(img, out_dir, name, "05_sources")


def draw_market_brief(out_dir, name, f):
    def shell(title):
        img = Image.new("RGB", (1080, 1080), BG)
        d = ImageDraw.Draw(img)
        _round(d, [58, 58, 1022, 1022], 28, PAPER, outline=LINE)
        d.rectangle([58, 58, 1022, 176], fill=NAVY)
        d.text((96, 96), title, fill=PAPER, font=f["h2"])
        return img, d

    img, d = shell("DAILY MARKET BRIEF")
    d.text((96, 260), NEWS["kicker"], fill=BLUE, font=f["h2"])
    d.text((96, 350), NEWS["headline"], fill=INK, font=f["display"], spacing=12)
    _round(d, [96, 800, 984, 906], 24, SOFT)
    d.text((134, 833), "출처  {}".format(NEWS["source"]), fill=MUTED, font=f["body"])
    _save(img, out_dir, name, "01_cover")

    img, d = shell("SUMMARY")
    _numbered_paragraphs(d, NEWS["summary"], 96, 245, f, style="report")
    _save(img, out_dir, name, "02_summary")

    img, d = shell("CHECK POINTS")
    _numbered_paragraphs(d, NEWS["points"], 96, 245, f, style="report")
    _save(img, out_dir, name, "03_points")

    img, d = shell("INVESTOR VIEW")
    _numbered_paragraphs(d, NEWS["opinion"], 96, 245, f, style="report")
    _save(img, out_dir, name, "04_investor")


def draw_clean_magazine(out_dir, name, f):
    def shell(title):
        img = Image.new("RGB", (1080, 1080), PAPER)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 26, 1080], fill=BLUE)
        d.text((84, 76), title, fill=BLUE, font=f["h2"])
        d.line([84, 135, 996, 135], fill=LINE, width=2)
        return img, d

    img, d = shell("ECONOMY NOTE")
    d.text((84, 235), NEWS["headline"], fill=INK, font=f["display"], spacing=12)
    d.text((84, 590), "숫자와 맥락을 함께 보는\n오늘의 경제 브리핑", fill=INK, font=f["h1"], spacing=14)
    d.text((84, 920), NEWS["source"], fill=MUTED, font=f["small"])
    _save(img, out_dir, name, "01_cover")

    img, d = shell("쉽게 말하면")
    _numbered_paragraphs(d, NEWS["summary"], 84, 230, f, style="underline")
    _save(img, out_dir, name, "02_summary")

    img, d = shell("체크할 부분")
    _numbered_paragraphs(d, NEWS["points"], 84, 230, f, style="underline")
    _save(img, out_dir, name, "03_points")

    img, d = shell("투자자 관점")
    _numbered_paragraphs(d, NEWS["opinion"], 84, 230, f, style="underline")
    _save(img, out_dir, name, "04_investor")


def draw_data_card(out_dir, name, f):
    def shell(title):
        img = Image.new("RGB", (1080, 1080), "#F8FAFD")
        d = ImageDraw.Draw(img)
        d.text((72, 72), "경제야 뭐했니", fill=MUTED, font=f["small"])
        d.text((72, 118), title, fill=BLUE, font=f["h2"])
        return img, d

    img, d = shell("오늘의 위험 신호")
    _round(d, [72, 205, 1008, 510], 36, BLUE)
    d.text((118, 260), "자영업자 빚,\n왜 다시 봐야 할까요?", fill=PAPER, font=f["title"], spacing=10)
    _round(d, [72, 610, 1008, 760], 28, PAPER, outline=LINE)
    d.text((118, 653), "연체 두 배 증가 · 금융채무 불이행자 94만 명", fill=INK, font=f["body_bold"])
    _save(img, out_dir, name, "01_cover")

    img, d = shell("3문장 브리핑")
    _numbered_paragraphs(d, NEWS["summary"], 72, 210, f, style="softbox")
    _save(img, out_dir, name, "02_summary")

    img, d = shell("핵심 포인트")
    _numbered_paragraphs(d, NEWS["points"], 72, 210, f, style="softbox")
    _save(img, out_dir, name, "03_points")

    img, d = shell("투자자 관점")
    _numbered_paragraphs(d, NEWS["opinion"], 72, 210, f, style="softbox")
    _save(img, out_dir, name, "04_investor")


def _numbered_paragraphs(d, paragraphs, x, y, f, style, accent=BLUE):
    for idx, paragraph in enumerate(paragraphs, start=1):
        if style == "line":
            number_font = f["h1"]
            number_text = "0{}".format(idx)
            number_x = x
            text_x = x + 76
            rule_right = 900
            max_width = rule_right - text_x
            lines = _wrap_to_width(d, paragraph, f["body"], max_width, max_lines=4)
            d.text((number_x, y), number_text, fill=accent, font=number_font)
            _draw_lines(d, lines, text_x, y + 7, f["body"], INK, 37)
            line_y = y + 26 + len(lines) * 37
            d.line([text_x, line_y, rule_right, line_y], fill=LINE, width=2)
            y += max(178, len(lines) * 37 + 94)
        elif style == "box":
            lines = _wrap_to_width(d, paragraph, f["body"], 830, max_lines=2)
            _round(d, [x, y, 1006, y + 170], 26, SOFT)
            d.text((x + 34, y + 44), str(idx), fill=accent, font=f["h2"])
            _draw_lines(d, lines, x + 105, y + 38, f["body"], INK, 43)
            y += 205
        elif style == "report":
            lines = _wrap_to_width(d, paragraph, f["body"], 700, max_lines=2)
            d.text((x, y), "0{}".format(idx), fill=accent, font=f["display"])
            _draw_lines(d, lines, x + 155, y + 14, f["body"], INK, 43)
            d.line([x + 155, y + 115, 950, y + 115], fill=LINE, width=2)
            y += 220
        elif style == "underline":
            lines = _wrap_to_width(d, paragraph, f["body"], 820, max_lines=2)
            _draw_lines(d, lines, x + 30, y, f["body"], INK, 45)
            d.rectangle([x + 30, y + 98, 900, y + 106], fill="#DDE7FF")
            y += 205
        elif style == "softbox":
            lines = _wrap_to_width(d, paragraph, f["body"], 780, max_lines=2)
            _round(d, [x, y, 1008, y + 178], 30, PAPER, outline=LINE)
            _round(d, [x + 36, y + 48, x + 96, y + 108], 30, accent)
            d.text((x + 55, y + 62), str(idx), fill=PAPER, font=f["small"])
            _draw_lines(d, lines, x + 130, y + 42, f["body"], INK, 43)
            y += 210


def _big_title(d, text, x, y, f, accent=BLUE):
    d.text((x, y), text, fill=INK, font=f["h1"])
    title_width = _text_width(d, text, f["h1"])
    d.rectangle([x, y + 64, x + title_width, y + 74], fill=accent)


def _source_background(f):
    source_path = Path("output") / "design_drafts" / "ai_source_card_background.png"
    if source_path.exists():
        img = Image.open(source_path).convert("RGB").resize((1080, 1080))
        overlay = Image.new("RGBA", (1080, 1080), (255, 255, 255, 120))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    else:
        img = Image.new("RGB", (1080, 1080), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1080, 38], fill=BLUE)
    button_text = "원문 보기"
    bbox = d.textbbox((0, 0), button_text, font=f["h2"])
    button_width = (bbox[2] - bbox[0]) + 110
    left = (1080 - button_width) // 2
    _round(d, [left, 245, left + button_width, 335], 45, BLUE)
    _center(d, button_text, 540, 268, f["h2"], PAPER)
    return img, d


def draw_font_preview(out_dir):
    candidates = _font_candidates()
    img = Image.new("RGB", (1080, 1380), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1080, 34], fill=BLUE)
    d.text((60, 70), "무료 한글 폰트 후보", fill=INK, font=_font(48, bold=True))
    d.text((60, 130), "같은 문장으로 제목/본문 느낌을 비교합니다.", fill=MUTED, font=_font(24))
    y = 210
    for name, regular, bold in candidates:
        try:
            title_font = ImageFont.truetype(str(bold), 43)
            body_font = ImageFont.truetype(str(regular), 27)
        except Exception:
            continue
        _round(d, [60, y, 1020, y + 190], 24, "#F8FAFD", outline=LINE)
        d.text((90, y + 26), name, fill=BLUE, font=_font(26, bold=True))
        d.text((90, y + 70), "자영업자 빚 부담 심화, 연체 두 배 증가", fill=INK, font=title_font)
        d.text((90, y + 132), "90일 이상 대출을 갚지 못한 자영업자가 늘고 있습니다.", fill=MUTED, font=body_font)
        y += 220
    img.save(out_dir / "font_preview.png")


def _draw_lines(d, lines, x, y, font, fill, step):
    for line in lines:
        d.text((x, y), line, fill=fill, font=font)
        y += step


def _wrap_to_width(d, text, font, max_width, max_lines):
    words = text.split(" ")
    lines = []
    current = ""

    for word in words:
        candidate = word if not current else current + " " + word
        if _text_width(d, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if _text_width(d, word, font) <= max_width:
            current = word
        else:
            pieces = _split_long_word(d, word, font, max_width)
            lines.extend(pieces[:-1])
            current = pieces[-1] if pieces else ""

    if current:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        # Keep the sentence complete in drafts by using smaller text upstream;
        # this fallback only protects the layout from overflow.
        lines[-1] = lines[-1].rstrip()
    return lines


def _split_long_word(d, word, font, max_width):
    pieces = []
    current = ""
    for char in word:
        candidate = current + char
        if _text_width(d, candidate, font) <= max_width:
            current = candidate
        else:
            if current:
                pieces.append(current)
            current = char
    if current:
        pieces.append(current)
    return pieces


def _text_width(d, text, font):
    bbox = d.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _center(d, text, center_x, y, font, fill):
    bbox = d.textbbox((0, 0), text, font=font)
    d.text((center_x - (bbox[2] - bbox[0]) / 2, y), text, fill=fill, font=font)


def _wrap(text, width, max_lines=2):
    import textwrap

    lines = textwrap.wrap(text, width=width, break_long_words=True, replace_whitespace=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip()
    return lines


def _round(d, box, radius, fill, outline=None):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline)


def _font(size, bold=False):
    pretendard = Path("assets") / "font_candidates" / "Pretendard" / "public" / "static" / "alternative"
    candidates = [
        pretendard / ("Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"),
        Path("C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf"),
        Path("assets/fonts/NotoSansKR-Bold.otf" if bold else "assets/fonts/NotoSansKR-Regular.otf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _font_candidates():
    base = Path("assets") / "font_candidates"
    return [
        ("Pretendard", base / "Pretendard" / "public" / "static" / "alternative" / "Pretendard-Regular.ttf", base / "Pretendard" / "public" / "static" / "alternative" / "Pretendard-Bold.ttf"),
        ("Noto Sans CJK KR", base / "NotoSansCJKkr-Regular.otf", base / "NotoSansCJKkr-Bold.otf"),
        ("IBM Plex Sans KR", base / "IBMPlexSansKR-Regular.ttf", base / "IBMPlexSansKR-Bold.ttf"),
        ("Nanum Gothic", base / "NanumGothic-Regular.ttf", base / "NanumGothic-Bold.ttf"),
        ("Gowun Dodum", base / "GowunDodum-Regular.ttf", base / "GowunDodum-Regular.ttf"),
    ]


def _save(img, out_dir, style, card):
    img.save(out_dir / "{}_{}.png".format(style, card))


if __name__ == "__main__":
    raise SystemExit(main())
