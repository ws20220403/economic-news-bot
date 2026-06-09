import unittest

from economic_news_bot import card_builder
from economic_news_bot.ai_processor import _coerce_sentences, _validate_payload, process_articles
from economic_news_bot.card_builder import BODY_SIZE, BODY_W, layout_problems
from economic_news_bot.main import _looks_like_fallback
from economic_news_bot.models import ArticleCandidate, ProcessedNews, SourceRef
from economic_news_bot.quality import validate_processed_news
from economic_news_bot.rss_fetcher import _is_relevant_candidate, _limit_by_source, dedupe_candidates

HAS_PIL = card_builder.Image is not None

LONG = "한국은행이 기준금리를 현 수준에서 유지하면서 물가와 환율 흐름을 더 지켜본 뒤 다음 행보를 결정하겠다는 신중한 태도를 분명히 했습니다."
GOOD = "이번 결정은 가계와 기업의 이자 부담은 물론 환율과 수출 경쟁력에도 영향을 줄 수 있어 함께 확인해야 합니다."


def _news(**overrides):
    base = dict(
        rank=1,
        headline="기준금리 동결",
        source="테스트",
        url="https://example.com/a",
        summary="\n".join([GOOD, GOOD, GOOD]),
        points=[GOOD, GOOD, GOOD],
        comment="\n".join([GOOD, GOOD, GOOD]),
        one_sentence="오늘 경제 흐름은 금리와 환율, 기업 비용 변화를 함께 확인해야 하는 상황입니다.",
        sources=[SourceRef(source="테스트", url="https://example.com/a", title="t")],
    )
    base.update(overrides)
    return ProcessedNews(**base)


class FallbackTests(unittest.TestCase):
    def test_fallback_limits_count_and_shape(self):
        candidates = [
            ArticleCandidate(title="금리 동결", url="https://example.com/1", source="A", summary="기준금리가 동결됐다."),
            ArticleCandidate(title="환율 상승", url="https://example.com/2", source="B", summary="환율이 상승했다."),
        ]
        processed = process_articles(candidates, {"news_count": 1, "use_ai": False}, force_fallback=True)
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0].rank, 1)
        self.assertEqual(len(processed[0].points), 3)

    def test_fallback_passes_quality_and_layout(self):
        candidates = [ArticleCandidate(title="국제유가 상승에 에너지 비용 부담 확대", url="https://example.com/oil", source="CNBC Economy", summary="유가가 올랐다.")]
        processed = process_articles(candidates, {"news_count": 1, "use_ai": False}, force_fallback=True)
        # Must not raise: the fallback editor produces card-safe text.
        validate_processed_news(processed, {"validate_card_layout": HAS_PIL})

    def test_fallback_handles_ellipsis_title(self):
        # News titles often end with "…"; the fallback must not produce a
        # "truncated" sentence that fails the dry-run quality gate.
        candidates = [ArticleCandidate(title="한달새 30% 폭락, 전쟁 상승분 다 토해낸 '이 원자재'…", url="https://example.com/x", source="매일경제", summary="")]
        processed = process_articles(candidates, {"news_count": 1, "use_ai": False}, force_fallback=True)
        validate_processed_news(processed, {"validate_card_layout": HAS_PIL})

    def test_publish_guard_detects_fallback(self):
        processed = process_articles(
            [ArticleCandidate(title="금리 뉴스", url="https://example.com", source="A", summary="금리 뉴스입니다.")],
            {"news_count": 1, "use_ai": False},
            force_fallback=True,
        )
        self.assertTrue(_looks_like_fallback(processed))


class CoercionTests(unittest.TestCase):
    def test_keeps_three(self):
        self.assertEqual(len(_coerce_sentences([GOOD, GOOD, GOOD])), 3)

    def test_splits_two_into_three(self):
        self.assertEqual(len(_coerce_sentences([LONG, LONG])), 3)

    def test_merges_four_into_three(self):
        short = "기준금리 동결로 가계와 기업의 이자 부담 흐름을 가늠하기가 한결 쉬워졌습니다."
        self.assertEqual(len(_coerce_sentences([short, short, short, short])), 3)

    def test_splits_multi_sentence_string(self):
        self.assertEqual(len(_coerce_sentences("{a} {a} {a}".format(a=GOOD))), 3)

    def test_validate_payload_normalizes(self):
        items = _validate_payload(
            [
                {
                    "headline": "매우 긴 헤드라인입니다 " * 5,
                    "source": "테스트",
                    "url": "https://example.com",
                    "summary": [GOOD, "2년 만의 변화가 가계와 기업 비용에 주는 압력을 구체적으로 짚어 설명하는 문장입니다.", GOOD],
                    "points": [GOOD, GOOD, GOOD],
                    "comment": "{a}\n{a}\n{a}".format(a=GOOD),
                    "one_sentence": "금리와 환율 변화가 생활비와 기업 비용에 미치는 영향을 한 번에 짚어야 하는 상황입니다.",
                    "sources": [{"source": "테스트", "url": "https://example.com", "title": "t"}],
                }
            ]
        )
        self.assertEqual(items[0].rank, 1)
        self.assertEqual(len(items[0].summary.splitlines()), 3)
        self.assertIn("2년", items[0].summary)
        self.assertEqual(len(items[0].comment.splitlines()), 3)


class QualityTests(unittest.TestCase):
    def test_rejects_truncated_sentence(self):
        item = _news(comment="\n".join([GOOD, GOOD, GOOD.replace("합니다.", "합니...")]))
        with self.assertRaises(ValueError):
            validate_processed_news([item], {"validate_card_layout": False})

    def test_rejects_wrong_sentence_count(self):
        item = _news(summary="\n".join([GOOD, GOOD]))
        with self.assertRaises(ValueError):
            validate_processed_news([item], {"validate_card_layout": False})

    def test_rejects_missing_source(self):
        item = _news(sources=[])
        with self.assertRaises(ValueError):
            validate_processed_news([item], {"validate_card_layout": False})


@unittest.skipUnless(HAS_PIL, "Pillow required for layout checks")
class LayoutTests(unittest.TestCase):
    def test_clean_item_has_no_layout_problems(self):
        self.assertEqual(layout_problems(_news()), [])

    def test_overlong_sentence_is_flagged(self):
        huge = ("매우긴문장" * 60) + "."
        self.assertTrue(layout_problems(_news(summary="\n".join([huge, GOOD, GOOD]))))

    def test_wrap_breaks_long_text(self):
        lines = card_builder._wrap(LONG, BODY_SIZE, False, BODY_W)
        self.assertGreater(len(lines), 1)


class RssTests(unittest.TestCase):
    def test_dedupe_removes_similar_titles(self):
        candidates = [
            ArticleCandidate(title="한국은행 기준금리 동결", url="https://example.com/1", source="A"),
            ArticleCandidate(title="한국은행, 기준금리 동결", url="https://example.com/2", source="B"),
            ArticleCandidate(title="국제유가 상승", url="https://example.com/3", source="C"),
        ]
        self.assertEqual(len(dedupe_candidates(candidates, 0.9)), 2)

    def test_limit_by_source_balances(self):
        candidates = [ArticleCandidate(title=f"A{i}", url=f"https://a/{i}", source="A") for i in range(5)] + [
            ArticleCandidate(title=f"B{i}", url=f"https://b/{i}", source="B") for i in range(2)
        ]
        limited = _limit_by_source(candidates, max_total=5, max_per_source=2)
        self.assertEqual([item.source for item in limited[:4]], ["A", "A", "B", "B"])
        self.assertEqual(len(limited), 5)

    def test_relevance_filter(self):
        society = ArticleCandidate(title="마이클 잭슨, 英 오피셜 차트 점령", url="https://www.mk.co.kr/news/culture/1", source="매일경제 증권")
        market = ArticleCandidate(title="국제유가 상승에 에너지 비용 부담 확대", url="https://www.example.com/world/energy", source="CNBC Economy")
        self.assertFalse(_is_relevant_candidate(society))
        self.assertTrue(_is_relevant_candidate(market))


if __name__ == "__main__":
    unittest.main()
