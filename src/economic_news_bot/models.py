from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ArticleCandidate:
    title: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    summary: str = ""


@dataclass
class SourceRef:
    source: str
    url: str
    title: str = ""


@dataclass
class ProcessedNews:
    rank: int
    headline: str
    source: str
    url: str
    summary: str
    points: List[str]
    comment: str
    one_sentence: str = ""
    sources: List[SourceRef] = field(default_factory=list)


@dataclass
class BuiltCardSet:
    rank: int
    source: str
    url: str
    files: List[str]
    caption: str
