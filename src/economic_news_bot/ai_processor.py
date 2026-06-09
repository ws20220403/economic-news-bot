import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Iterable, List, Optional

from .models import ArticleCandidate, ProcessedNews, SourceRef
from .quality import (
    BODY_MAX_CHARS,
    BODY_MIN_CHARS,
    COVER_MAX_CHARS,
    HEADLINE_MAX_CHARS,
    validate_processed_news,
)

SENTENCES_PER_BLOCK = 3
ELLIPSES = ("...", "…", "⋯")


def process_articles(candidates: Iterable[ArticleCandidate], config: dict, force_fallback: bool = False) -> List[ProcessedNews]:
    candidates = list(candidates)
    news_count = int(config.get("news_count", 6))
    api_key = os.environ.get("GEMINI_API_KEY")

    if api_key and config.get("use_ai", True) and not force_fallback:
        models = _model_chain(config)
        attempts = max(1, int(config.get("gemini_attempts", 3)))
        last_error = None
        for attempt in range(1, attempts + 1):
            for model in models:  # fall through to a backup model when one is overloaded
                try:
                    items = _process_with_gemini(candidates, config, api_key, model)[:news_count]
                    validate_processed_news(items, config)
                    return _renumber(items)
                except Exception as exc:  # noqa: BLE001 - we want to retry on any failure
                    last_error = exc
                    print("[WARN] Gemini attempt {} via {} failed. ({})".format(attempt, model, str(exc)[:160]))
            if attempt < attempts:
                wait_seconds = 5 * attempt
                print("[WARN] Retrying Gemini in {}s.".format(wait_seconds))
                time.sleep(wait_seconds)
        print("[WARN] Gemini processing failed after {} attempt(s); fallback editor used. ({})".format(attempts, str(last_error)[:160]))

    return _process_with_fallback(candidates, news_count)


def _model_chain(config: dict) -> List[str]:
    chain = [str(config.get("model", "gemini-2.5-flash"))]
    for fallback in config.get("model_fallbacks", ["gemini-2.0-flash"]):
        if fallback and fallback not in chain:
            chain.append(str(fallback))
    return chain


# ---------------------------------------------------------------------------
# Gemini REST call
# ---------------------------------------------------------------------------

def _process_with_gemini(candidates: List[ArticleCandidate], config: dict, api_key: str, model: str) -> List[ProcessedNews]:
    prompt = _build_prompt(candidates, int(config.get("news_count", 6)))
    url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=int(config.get("gemini_timeout_seconds", 120))) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("Gemini REST API failed: HTTP {} {}".format(exc.code, body[:500]))

    text = _extract_gemini_text(raw)
    payload = _extract_json(text)
    return _validate_payload(payload)


_RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "headline": {"type": "STRING"},
            "one_sentence": {"type": "STRING"},
            "summary": {"type": "ARRAY", "items": {"type": "STRING"}},
            "points": {"type": "ARRAY", "items": {"type": "STRING"}},
            "comment": {"type": "ARRAY", "items": {"type": "STRING"}},
            "sources": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "source": {"type": "STRING"},
                        "url": {"type": "STRING"},
                        "title": {"type": "STRING"},
                    },
                    "required": ["source", "url"],
                },
            },
        },
        "required": ["headline", "one_sentence", "summary", "points", "comment", "sources"],
    },
}


def _build_prompt(candidates: List[ArticleCandidate], news_count: int) -> str:
    compact_articles = []
    for idx, article in enumerate(candidates[:40], start=1):
        compact_articles.append(
            {
                "id": idx,
                "title": article.title,
                "source": article.source,
                "url": article.url,
                "summary": article.summary[:500],
            }
        )

    return (
        "너는 한국어 경제 뉴스 에디터다. 독자는 경제 초보자다.\n"
        "아래 RSS 후보를 묶어 오늘 아침 독자가 먼저 알아야 할 경제 이슈 {count}개를 골라 카드뉴스 문안으로 재작성하라.\n"
        "같은 사건이나 같은 경제 흐름을 다룬 기사는 하나의 이슈로 묶고, 가능하면 한 이슈에 복수 출처를 붙인다.\n"
        "가능하면 국내 정책/시장, 국내 기업/산업, 해외 경제/시장 이슈가 골고루 섞이게 고른다.\n"
        "한 이슈에는 하나의 주제만 담아라. 성격이 다른 사건(예: M&A 지연과 유턴기업 지원)을 한 카드에 섞지 마라.\n"
        "정부 정책도 '정책 묶음'으로 뭉뚱그리지 말고 서로 다른 정책은 별도 이슈로 분리한다.\n"
        "관련 출처가 하나뿐이면 sources를 1개만 넣어도 된다. 복수 출처를 만들려고 무관한 기사를 붙이지 마라.\n\n"
        "[사실성 규칙]\n"
        "- 근거는 후보의 title, summary, source, url 안의 정보로만 삼고, 모르는 수치나 사실은 만들지 마라.\n"
        "- summary가 비어 있는 후보는 title에서 확인되는 내용만 쓰고, 본문을 읽은 듯 세부를 추정하지 마라.\n"
        "- 전쟁, 위기, 급락, 폭등 같은 강한 표현은 후보 문구에 명시된 경우에만 쓴다.\n"
        "- 전망/논의/우려는 사실처럼 단정하지 말고 '영향을 볼 수 있다/확인해야 한다'처럼 조심스럽게 쓴다.\n"
        "- 투자 권유(매수/매도 추천)는 금지한다.\n"
        "- 후보 기사의 source와 url은 글자 그대로 복사하고, sources에는 실제로 참고한 기사만 넣는다.\n\n"
        "[문장 규칙 - 매우 중요]\n"
        "- summary, points, comment는 각각 정확히 {sentences}개의 문장을 담은 문자열 배열이다. 더도 덜도 안 된다.\n"
        "- 각 문장은 공백 포함 {min}~{max}자 사이의 완결된 한 문장이며, 반드시 마침표로 끝낸다.\n"
        "- 말줄임표(…)나 중간에 끊긴 문장을 쓰지 마라. 한 문장 안에 원인·현재 상황·영향을 압축해 설명한다.\n"
        "- 제목만 반복하지 말고 '무슨 일인지', '왜 중요한지', '무엇을 볼지'가 드러나게 쓴다.\n\n"
        "[필드 설명]\n"
        "- headline: 표지 제목. 한국어 {headline}자 이내, 마침표 없이.\n"
        "- one_sentence: 표지 한 줄 요약. {cover}자 이내, 마침표로 끝낸다.\n"
        "- summary: 쉬운 요약 {sentences}문장 배열.\n"
        "- points: 핵심 포인트 {sentences}문장 배열.\n"
        "- comment: 투자자 관점 {sentences}문장 배열(특정 종목 매매 권유 금지).\n"
        "- sources: [{{source, url, title}}] 배열, 1~4개. 후보 기사 값을 그대로 사용한다.\n\n"
        "Articles:\n{articles}"
    ).format(
        count=news_count,
        sentences=SENTENCES_PER_BLOCK,
        min=BODY_MIN_CHARS,
        max=BODY_MAX_CHARS,
        headline=HEADLINE_MAX_CHARS,
        cover=COVER_MAX_CHARS,
        articles=json.dumps(compact_articles, ensure_ascii=False),
    )


def _extract_json(text: str):
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def _extract_gemini_text(payload: dict) -> str:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini response did not contain text candidates: {}".format(payload)) from exc
    chunks = [part.get("text", "") for part in parts if isinstance(part, dict)]
    text = "\n".join(chunk for chunk in chunks if chunk).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty text response.")
    return text


# ---------------------------------------------------------------------------
# Payload normalisation
# ---------------------------------------------------------------------------

def _validate_payload(payload) -> List[ProcessedNews]:
    if not isinstance(payload, list):
        raise ValueError("Gemini payload must be a JSON array.")

    items = []
    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            raise ValueError("News item must be an object.")
        sources = _normalize_sources(raw)
        primary_source = _clean_inline(str(raw.get("source") or (sources[0].source if sources else "")), 24)
        primary_url = str(raw.get("url") or (sources[0].url if sources else "")).strip()

        item = ProcessedNews(
            rank=index,
            headline=_clean_inline(str(raw.get("headline") or ""), HEADLINE_MAX_CHARS),
            source=primary_source,
            url=primary_url,
            summary="\n".join(_coerce_sentences(raw.get("summary"))),
            points=_coerce_sentences(raw.get("points")),
            comment="\n".join(_coerce_sentences(raw.get("comment"))),
            one_sentence=_finish_sentence(_clean_inline(str(raw.get("one_sentence") or ""), COVER_MAX_CHARS)),
            sources=sources,
        )
        if not item.sources and item.source and item.url:
            item.sources = [SourceRef(source=item.source, url=item.url, title=item.headline)]
        if item.headline and item.sources:
            items.append(item)
    if not items:
        raise ValueError("Gemini payload produced no usable news items.")
    return _renumber(items)


def _normalize_sources(raw: dict) -> List[SourceRef]:
    raw_sources = raw.get("sources") or []
    sources = []
    if isinstance(raw_sources, list):
        for source_item in raw_sources[:4]:
            if not isinstance(source_item, dict):
                continue
            source = _clean_inline(str(source_item.get("source") or ""), 24)
            url = str(source_item.get("url") or "").strip()
            title = _clean_inline(str(source_item.get("title") or ""), 70)
            if source and url:
                sources.append(SourceRef(source=source, url=url, title=title))
    if not sources and raw.get("source") and raw.get("url"):
        sources.append(
            SourceRef(
                source=_clean_inline(str(raw.get("source")), 24),
                url=str(raw.get("url")).strip(),
                title=_clean_inline(str(raw.get("headline") or ""), 70),
            )
        )
    return sources


def _coerce_sentences(value) -> List[str]:
    """Turn any AI field into exactly SENTENCES_PER_BLOCK complete sentences.

    Handles arrays, multi-sentence strings, too few, and too many sentences so a
    slightly off-spec model response never sinks the whole batch.
    """
    sentences = _to_sentence_list(value)
    if not sentences:
        raise ValueError("text block is empty.")

    while len(sentences) > SENTENCES_PER_BLOCK:
        sentences = _merge_shortest_neighbour(sentences)
    while len(sentences) < SENTENCES_PER_BLOCK:
        if not _split_longest(sentences):
            break
    if len(sentences) != SENTENCES_PER_BLOCK:
        raise ValueError("could not normalise text into {} sentences.".format(SENTENCES_PER_BLOCK))

    cleaned = [_finish_sentence(sentence) for sentence in sentences]
    for sentence in cleaned:
        if any(marker in sentence for marker in ELLIPSES):
            raise ValueError("sentence looks truncated.")
        if not (BODY_MIN_CHARS - 10) <= len(sentence) <= (BODY_MAX_CHARS + 15):
            raise ValueError("sentence length {} is out of range.".format(len(sentence)))
    return cleaned


def _to_sentence_list(value) -> List[str]:
    if isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raw_items = str(value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")

    sentences: List[str] = []
    for chunk in raw_items:
        chunk = _strip_bullet(chunk)
        if not chunk:
            continue
        sentences.extend(_split_sentences(chunk))
    return [s for s in (_clean_ws(s) for s in sentences) if s]


def _split_sentences(value: str) -> List[str]:
    value = _clean_ws(value)
    if not value:
        return []
    parts = re.split(r"(?<=[.!?])\s+", value)
    return [part.strip() for part in parts if part.strip()]


def _merge_shortest_neighbour(sentences: List[str]) -> List[str]:
    best_index = 0
    best_len = None
    for i in range(len(sentences) - 1):
        combined = len(sentences[i]) + len(sentences[i + 1])
        if best_len is None or combined < best_len:
            best_len = combined
            best_index = i
    merged = _finish_sentence(sentences[best_index]) + " " + sentences[best_index + 1]
    return sentences[:best_index] + [merged] + sentences[best_index + 2:]


def _split_longest(sentences: List[str]) -> bool:
    longest_index = max(range(len(sentences)), key=lambda i: len(sentences[i]))
    pieces = _split_in_two(sentences[longest_index])
    if not pieces:
        return False
    sentences[longest_index:longest_index + 1] = pieces
    return True


def _split_in_two(sentence: str) -> Optional[List[str]]:
    sentence = _clean_ws(sentence)
    if len(sentence) < 2 * (BODY_MIN_CHARS - 10):
        return None
    target = len(sentence) // 2
    # Prefer a clause boundary (comma) closest to the middle, else a space.
    boundaries = [m.end() for m in re.finditer(r"[,，]\s*", sentence)]
    if not boundaries:
        boundaries = [m.start() for m in re.finditer(r"\s", sentence)]
    if not boundaries:
        return None
    cut = min(boundaries, key=lambda pos: abs(pos - target))
    first = _clean_ws(sentence[:cut]).rstrip(",，")
    second = _clean_ws(sentence[cut:])
    if not first or not second:
        return None
    return [_finish_sentence(first), _finish_sentence(second)]


# ---------------------------------------------------------------------------
# Fallback editor (no API key / dry-run)
# ---------------------------------------------------------------------------

def _process_with_fallback(candidates: List[ArticleCandidate], news_count: int) -> List[ProcessedNews]:
    output = []
    for rank, article in enumerate(candidates[:news_count], start=1):
        base = _clean_ws(article.summary or article.title)
        headline = _clean_inline(article.title, HEADLINE_MAX_CHARS)
        topic = _trim_plain(article.title, 26)
        summary = [
            "{} 소식으로, 오늘 아침 살펴볼 만한 경제 이슈로 후보 기사에서 추려 정리한 항목입니다.".format(topic),
            "이 카드는 AI 키 없이 만든 점검용 요약이라 세부 수치와 맥락은 원문에서 다시 확인해야 합니다.".format(),
            "실제 발송 전에는 Gemini 요약을 켜고 내용이 정확한지 한 번 더 검토하는 것이 좋습니다.".format(),
        ]
        points = [
            "{} 흐름이 시장과 정책에 어떤 영향을 주는지 원문에서 핵심 맥락을 확인해 두는 것이 좋습니다.".format(topic),
            "관련 수치와 일정은 점검용 카드에 담기지 않으므로 원문 링크에서 직접 살펴봐야 정확합니다.".format(),
            "비슷한 다른 기사와 함께 비교하면 이 이슈의 중요도와 파급 범위를 더 분명히 가늠할 수 있습니다.".format(),
        ]
        comment = [
            "점검용 요약이므로 투자 판단의 근거로 삼기보다 원문 수치와 시장 반응을 먼저 확인해야 합니다.".format(),
            "특정 종목 매매를 권하기보다 이 이슈가 관련 업종 전반에 주는 방향성을 살피는 편이 안전합니다.".format(),
            "단기 가격 변동보다 흐름이 이어지는지, 추가 발표가 있는지 차분히 지켜보는 관점이 필요합니다.".format(),
        ]
        output.append(
            ProcessedNews(
                rank=rank,
                headline=headline,
                source=article.source,
                url=article.url,
                summary="\n".join(_finish_sentence(s) for s in summary),
                points=[_finish_sentence(s) for s in points],
                comment="\n".join(_finish_sentence(s) for s in comment),
                one_sentence=_fallback_cover(base, topic),
                sources=[SourceRef(source=article.source, url=article.url, title=article.title)],
            )
        )
    return output


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------

def _strip_bullet(value: str) -> str:
    return re.sub(r"^\s*(?:[-•*]\s+|\d+[.)]\s+)", "", value or "").strip()


def _clean_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clean_inline(value: str, limit: int) -> str:
    value = _clean_ws(_strip_bullet(value))
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _trim_plain(value: str, limit: int) -> str:
    """Truncate to a word boundary without adding an ellipsis marker."""
    value = _clean_ws(value)
    if len(value) <= limit:
        return value
    cut = value[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.strip()


def _fallback_cover(base: str, topic: str) -> str:
    first = _split_sentences(base)
    if first and 18 <= len(first[0]) <= COVER_MAX_CHARS:
        return _finish_sentence(first[0])
    text = "{} 관련 소식을 오늘 아침 경제 이슈로 추려 정리했습니다".format(topic)
    return _finish_sentence(_trim_plain(text, COVER_MAX_CHARS))


def _finish_sentence(value: str) -> str:
    value = _clean_ws(value)
    if not value:
        return value
    if value[-1] in ".!?。？！":
        return value
    return value + "."


def _renumber(items: List[ProcessedNews]) -> List[ProcessedNews]:
    for index, item in enumerate(items, start=1):
        item.rank = index
    return items
