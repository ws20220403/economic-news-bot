import json
import os
import re
import urllib.error
import urllib.request
from typing import Iterable, List

from .models import ArticleCandidate, ProcessedNews, SourceRef


def process_articles(candidates: Iterable[ArticleCandidate], config: dict, force_fallback: bool = False) -> List[ProcessedNews]:
    candidates = list(candidates)
    news_count = int(config.get("news_count", 6))
    api_key = os.environ.get("GEMINI_API_KEY")

    if api_key and config.get("use_ai", True) and not force_fallback:
        try:
            return _process_with_gemini(candidates, config, api_key)[:news_count]
        except Exception as exc:
            print("[WARN] Gemini processing failed; fallback editor used. ({})".format(exc))

    return _process_with_fallback(candidates, news_count)


def _process_with_gemini(candidates: List[ArticleCandidate], config: dict, api_key: str) -> List[ProcessedNews]:
    try:
        from google import genai  # type: ignore
    except ImportError:
        return _process_with_gemini_rest(candidates, config, api_key)

    model = config.get("model", "gemini-2.5-flash")
    prompt = _build_prompt(candidates, int(config.get("news_count", 6)))
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    payload = _extract_json(getattr(response, "text", ""))
    return _validate_payload(payload)


def _process_with_gemini_rest(candidates: List[ArticleCandidate], config: dict, api_key: str) -> List[ProcessedNews]:
    model = config.get("model", "gemini-2.5-flash")
    prompt = _build_prompt(candidates, int(config.get("news_count", 6)))
    url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("Gemini REST API failed: HTTP {} {}".format(exc.code, body[:500]))

    text = _extract_gemini_text(raw)
    payload = _extract_json(text)
    return _validate_payload(payload)


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
        "아래 RSS 후보를 묶어 오늘 아침 독자가 먼저 알아야 할 경제 이슈 {count}개를 골라 카드뉴스용 문안으로 재작성하라.\n"
        "같은 사건이나 같은 경제 흐름을 다룬 기사는 하나의 이슈로 묶고, 가능한 경우 한 이슈에 복수 출처를 붙인다.\n"
        "가능하면 국내 정책/시장, 국내 기업/산업, 해외 경제/시장 이슈가 섞이게 고른다.\n"
        "같은 출처가 과도하게 몰리면 중요도가 비슷한 다른 출처 기사로 대체한다.\n"
        "근거는 후보의 title, summary, source, url 안에 있는 정보로만 삼고, 모르는 수치나 사실은 만들지 마라.\n"
        "summary가 비어 있는 후보는 title에서 직접 확인되는 내용만 사용하고, 기사 본문을 읽은 것처럼 세부 내용을 추정하지 마라.\n"
        "전쟁, 위기, 급락, 폭등처럼 강한 표현은 후보 문구에 명시된 경우에만 쓰고, 전망/논의/우려는 사실처럼 단정하지 마라.\n"
        "여러 기사를 묶을 때 서로 직접 관련이 약하면 억지로 하나의 이슈로 만들지 말고 별도 이슈로 둔다.\n"
        "한 이슈 안에는 하나의 주제만 담아라. 예를 들어 M&A 지연과 유턴기업 지원처럼 성격이 다른 사건을 한 카드에 섞지 마라.\n"
        "정부 정책도 '정책 묶음'으로 뭉뚱그리지 말고, 유턴기업 지원, 에너지 가격 정책, 금융 안정 제도처럼 서로 다른 정책은 별도 이슈로 분리한다.\n"
        "관련 출처가 하나뿐이면 sources를 1개만 넣어도 된다. 복수 출처를 만들기 위해 무관한 기사를 붙이지 마라.\n"
        "투자 권유 표현은 금지하고, '영향을 볼 수 있다/확인해야 한다'처럼 조심스럽게 쓴다.\n"
        "문장은 짧고 쉬워야 한다. 전문 용어가 나오면 괄호로 쉽게 풀어쓴다.\n"
        "말줄임표(…)를 쓰거나 문장을 중간에 끊지 말고, 모든 문장은 완전한 마침표 문장으로 끝낸다.\n"
        "후보 기사에 있는 source와 url은 반드시 그대로 복사하고, sources 배열에는 실제로 참고한 기사만 넣는다.\n"
        "제목만 반복하지 말고 '무슨 일이 있었는지', '왜 중요한지', '독자가 볼 포인트'가 드러나게 쓴다.\n"
        "Return JSON only, as an array of objects with these fields: "
        "rank, headline, one_sentence, source, url, sources, summary, points, comment.\n"
        "headline: 한국어 30자 이내.\n"
        "one_sentence: 표지에 들어갈 한 문장 요약, 55자 안팎, 마침표로 끝낸다.\n"
        "source/url: 대표 출처 1개의 source와 url.\n"
        "sources: [{{source, url, title}}] 형식 배열, 1~4개. 후보 기사 값을 그대로 사용한다.\n"
        "summary: 쉬운 요약 정확히 3문장, 각 문장은 상세하지만 70자 안팎, 줄바꿈은 \\n, 모든 문장은 마침표로 끝낸다.\n"
        "points: 핵심 포인트 정확히 3개, 각 70자 안팎, 모든 문장은 마침표로 끝낸다.\n"
        "comment: 투자자 관점 정확히 3문장, 각 70자 안팎, 줄바꿈은 \\n, 특정 매수/매도 권유 금지.\n\n"
        "Articles:\n{articles}"
    ).format(count=news_count, articles=json.dumps(compact_articles, ensure_ascii=False))


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


def _validate_payload(payload) -> List[ProcessedNews]:
    if not isinstance(payload, list):
        raise ValueError("Gemini payload must be a JSON array.")

    items = []
    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            raise ValueError("News item must be an object.")
        points = raw.get("points") or []
        if not isinstance(points, list) or len(points) != 3:
            raise ValueError("points must contain exactly three strings.")
        sources = _normalize_sources(raw)
        primary_source = _clean_output_text(str(raw.get("source") or (sources[0].source if sources else "")), 24, 1)
        primary_url = str(raw.get("url") or (sources[0].url if sources else "")).strip()
        item = ProcessedNews(
            rank=int(raw.get("rank") or index),
            headline=_clean_output_text(str(raw.get("headline") or ""), 34, 1),
            source=primary_source,
            url=primary_url,
            summary="\n".join(_clean_sentence_list(raw.get("summary"), 3, 150)),
            points=[_clean_output_text(str(point), 120, 1) for point in points[:3]],
            comment="\n".join(_clean_sentence_list(raw.get("comment"), 3, 150)),
            one_sentence=_clean_output_text(str(raw.get("one_sentence") or ""), 100, 1),
            sources=sources,
        )
        if not item.sources and item.source and item.url:
            item.sources = [SourceRef(source=item.source, url=item.url, title=item.headline)]
        if item.headline and item.source and item.url:
            items.append(item)
    return _renumber(items)


def _normalize_sources(raw: dict) -> List[SourceRef]:
    raw_sources = raw.get("sources") or []
    sources = []
    if isinstance(raw_sources, list):
        for source_item in raw_sources[:4]:
            if not isinstance(source_item, dict):
                continue
            source = _clean_output_text(str(source_item.get("source") or ""), 24, 1)
            url = str(source_item.get("url") or "").strip()
            title = _clean_output_text(str(source_item.get("title") or ""), 60, 1)
            if source and url:
                sources.append(SourceRef(source=source, url=url, title=title))
    if not sources and raw.get("source") and raw.get("url"):
        sources.append(
            SourceRef(
                source=_clean_output_text(str(raw.get("source")), 24, 1),
                url=str(raw.get("url")).strip(),
                title=_clean_output_text(str(raw.get("headline") or ""), 60, 1),
            )
        )
    return sources


def _join_text(value) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value or "")


def _clean_sentence_list(value, max_items: int, line_limit: int) -> List[str]:
    text = _join_text(value)
    candidates = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = re.sub(r"^\s*(?:[-•]\s+|\d+[.)]\s+)", "", line).strip()
        if not line:
            continue
        candidates.extend(_split_sentences(line))
    if not candidates:
        candidates = [text]
    cleaned = []
    for sentence in candidates:
        sentence = _clean_output_text(sentence, line_limit, 1)
        if sentence:
            cleaned.append(_ensure_period(sentence))
        if len(cleaned) >= max_items:
            break
    return cleaned


def _split_sentences(value: str) -> List[str]:
    value = re.sub(r"\s+", " ", value or "").strip()
    if not value:
        return []
    parts = re.split(r"(?<=[.!?。？！])\s+", value)
    if len(parts) == 1:
        parts = re.split(r"(?<=다\.)\s*", value)
    return [part.strip() for part in parts if part.strip()]


def _ensure_period(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if value[-1] in ".!?。？！":
        return value
    return value + "."


def _process_with_fallback(candidates: List[ArticleCandidate], news_count: int) -> List[ProcessedNews]:
    output = []
    for rank, article in enumerate(candidates[:news_count], start=1):
        base = article.summary or article.title
        output.append(
            ProcessedNews(
                rank=rank,
                headline=_trim(article.title, 32),
                source=article.source,
                url=article.url,
                summary=_fallback_summary(article.title, base),
                points=[
                    _trim(article.title, 28),
                    "시장과 정책 영향을 확인",
                    "원문에서 세부 수치 확인",
                ],
                comment=(
                    "이 항목은 AI 키 없이 만든 dry-run 요약입니다.\n"
                    "실제 운영 전 원문과 수치를 다시 확인하세요.\n"
                    "투자 판단 전 시장 반응과 관련 지표를 함께 봐야 합니다."
                ),
                one_sentence=_trim(base, 58),
                sources=[SourceRef(source=article.source, url=article.url, title=article.title)],
            )
        )
    return output


def _fallback_summary(title: str, body: str) -> str:
    clean = re.sub(r"\s+", " ", body).strip()
    return "\n".join(
        [
            _trim(title, 36),
            _trim(clean, 44),
            "자세한 내용은 원문 링크에서 확인이 필요합니다.",
        ]
    )


def _trim(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _clean_output_text(value: str, line_limit: int, max_lines: int) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = []
    for line in value.splitlines() or [value]:
        line = re.sub(r"^\s*(?:[-•*]\s+|\d+[.)]\s+)", "", line).strip()
        line = re.sub(r"\s+", " ", line)
        if line:
            raw_lines.append(_trim(line, line_limit))
    if not raw_lines:
        return ""
    return "\n".join(raw_lines[:max_lines])


def _renumber(items: List[ProcessedNews]) -> List[ProcessedNews]:
    for index, item in enumerate(items, start=1):
        item.rank = index
    return items
