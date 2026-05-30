import html
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List, Optional

from .models import ArticleCandidate


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
ECONOMIC_KEYWORDS = (
    "경제", "금리", "환율", "증시", "주식", "코스피", "코스닥", "나스닥", "다우", "시장",
    "투자", "물가", "인플레이션", "유가", "에너지", "원전", "수출", "수입", "반도체",
    "AI", "로봇", "기업", "산업", "제조", "공급망", "소비", "내수", "자영업", "소상공인",
    "대출", "연체", "부채", "세금", "과세", "연금", "재정", "정책", "규제", "고용",
    "earnings", "stocks", "markets", "inflation", "energy", "oil", "rates", "economy",
    "consumer", "prices", "stagflation", "tariff",
)
EXCLUDED_URL_PARTS = ("/news/society/", "/news/culture/")
EXCLUDED_TITLE_KEYWORDS = (
    "[포토]", "마이클 잭슨", "로제", "오피셜 차트", "여책저책", "건강검진", "주치의",
    "체중", "소림사", "전 주지", "장애인 종업원", "성매매", "추모",
)


def fetch_candidates(config: Dict, hours: int = 36) -> List[ArticleCandidate]:
    sources = [source for source in config.get("rss_sources", []) if source.get("enabled", True)]
    candidates = []

    for source in sources:
        try:
            candidates.extend(_fetch_one_source(source, hours=hours))
        except Exception as exc:
            print("[WARN] RSS source skipped: {} ({})".format(source.get("name", "unknown"), exc))

    candidates = [candidate for candidate in candidates if _is_relevant_candidate(candidate)]
    deduped = dedupe_candidates(candidates, config.get("dedupe_threshold", 0.86))
    deduped.sort(key=lambda item: item.published_at or datetime.min, reverse=True)
    return _limit_by_source(
        deduped,
        max_total=int(config.get("max_candidates", 40)),
        max_per_source=int(config.get("max_candidates_per_source", 12)),
    )


def dedupe_candidates(candidates: Iterable[ArticleCandidate], threshold: float) -> List[ArticleCandidate]:
    kept = []
    for candidate in candidates:
        normalized = _normalize_title(candidate.title)
        if not normalized:
            continue
        duplicate = False
        for existing in kept:
            score = SequenceMatcher(None, normalized, _normalize_title(existing.title)).ratio()
            if score >= threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
    return kept


def _limit_by_source(candidates: List[ArticleCandidate], max_total: int, max_per_source: int) -> List[ArticleCandidate]:
    if max_per_source <= 0:
        return candidates[:max_total]

    selected = []
    per_source = {}
    leftovers = []
    for candidate in candidates:
        count = per_source.get(candidate.source, 0)
        if count < max_per_source:
            selected.append(candidate)
            per_source[candidate.source] = count + 1
        else:
            leftovers.append(candidate)
        if len(selected) >= max_total:
            return selected

    for candidate in leftovers:
        selected.append(candidate)
        if len(selected) >= max_total:
            break
    return selected


def _is_relevant_candidate(candidate: ArticleCandidate) -> bool:
    text = "{} {} {}".format(candidate.title, candidate.summary, candidate.source).lower()
    title = candidate.title.lower()
    url = candidate.url.lower()

    if any(part in url for part in EXCLUDED_URL_PARTS):
        return False
    if any(keyword.lower() in title for keyword in EXCLUDED_TITLE_KEYWORDS):
        return False
    if "경제" in candidate.source or "economy" in candidate.source.lower():
        return True
    return any(keyword.lower() in text for keyword in ECONOMIC_KEYWORDS)


def _fetch_one_source(source: Dict, hours: int) -> List[ArticleCandidate]:
    try:
        import feedparser  # type: ignore
    except ImportError:
        return _fetch_with_stdlib(source, hours)

    parsed = feedparser.parse(source["url"])
    if getattr(parsed, "bozo", 0):
        print("[WARN] feedparser failed for {}; stdlib parser fallback will be used. ({})".format(source["name"], getattr(parsed, "bozo_exception", "feedparser parse error")))
        return _fetch_with_stdlib(source, hours)

    now = datetime.utcnow()
    cutoff = now - timedelta(hours=hours)
    items = []
    for entry in parsed.entries:
        published_at = _parse_struct_time(getattr(entry, "published_parsed", None))
        if published_at and published_at < cutoff:
            continue
        title = _clean_text(getattr(entry, "title", ""))
        url = getattr(entry, "link", "")
        summary = _clean_text(getattr(entry, "summary", ""))
        if title and url:
            items.append(ArticleCandidate(title=title, url=url, source=source["name"], published_at=published_at, summary=summary))
    return items


def _fetch_with_stdlib(source: Dict, hours: int) -> List[ArticleCandidate]:
    request = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "economic-news-bot/0.1 (+https://github.com/)"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read()

    if b"<rss" not in body[:500].lower() and b"<feed" not in body[:500].lower():
        raise RuntimeError("URL did not return RSS/Atom content ({})".format(content_type))

    text = body.decode("utf-8", errors="replace")
    text = _sanitize_xml_entities(text)
    root = ET.fromstring(text)
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=hours)

    items = []
    if root.tag.endswith("rss"):
        raw_items = root.findall("./channel/item")
        for item in raw_items:
            title = _clean_text(_find_text(item, "title"))
            url = _find_text(item, "link").strip()
            summary = _clean_text(_find_text(item, "description"))
            published_at = _parse_date(_find_text(item, "pubDate"))
            if published_at and published_at < cutoff:
                continue
            if title and url:
                items.append(ArticleCandidate(title=title, url=url, source=source["name"], published_at=published_at, summary=summary))
        return items

    for item in root.findall("{http://www.w3.org/2005/Atom}entry"):
        title = _clean_text(_find_text(item, "{http://www.w3.org/2005/Atom}title"))
        url = ""
        for link in item.findall("{http://www.w3.org/2005/Atom}link"):
            if link.attrib.get("href"):
                url = link.attrib["href"]
                break
        summary = _clean_text(_find_text(item, "{http://www.w3.org/2005/Atom}summary"))
        published_at = _parse_date(_find_text(item, "{http://www.w3.org/2005/Atom}updated"))
        if published_at and published_at < cutoff:
            continue
        if title and url:
            items.append(ArticleCandidate(title=title, url=url, source=source["name"], published_at=published_at, summary=summary))
    return items


def _find_text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    return child.text if child is not None and child.text else ""


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = TAG_RE.sub(" ", value)
    return SPACE_RE.sub(" ", value).strip()


def _normalize_title(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value).lower()


def _sanitize_xml_entities(value: str) -> str:
    allowed = {"amp", "lt", "gt", "quot", "apos"}

    def replace(match):
        entity_name = match.group(1)
        if entity_name in allowed or entity_name.startswith("#"):
            return match.group(0)
        unescaped = html.unescape(match.group(0))
        return "" if unescaped == match.group(0) else unescaped

    return re.sub(r"&([A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);", replace, value)


def _parse_struct_time(value) -> Optional[datetime]:
    if not value:
        return None
    return datetime.utcfromtimestamp(time.mktime(value))


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.replace(tzinfo=None)
    except Exception:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
