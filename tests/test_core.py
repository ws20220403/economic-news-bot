import unittest

from economic_news_bot.ai_processor import _validate_payload, process_articles
from economic_news_bot.card_builder import wrap_text
from economic_news_bot.main import _looks_like_fallback
from economic_news_bot.models import ArticleCandidate
from economic_news_bot.rss_fetcher import _is_relevant_candidate, _limit_by_source, dedupe_candidates


class CoreTests(unittest.TestCase):
    def test_fallback_processing_limits_count(self):
        candidates = [
            ArticleCandidate(title="금리 동결", url="https://example.com/1", source="A", summary="기준금리가 동결됐다."),
            ArticleCandidate(title="환율 상승", url="https://example.com/2", source="B", summary="환율이 상승했다."),
        ]
        processed = process_articles(candidates, {"news_count": 1, "use_ai": False}, force_fallback=True)
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0].rank, 1)
        self.assertEqual(len(processed[0].points), 3)

    def test_dedupe_candidates_removes_similar_titles(self):
        candidates = [
            ArticleCandidate(title="한국은행 기준금리 동결", url="https://example.com/1", source="A"),
            ArticleCandidate(title="한국은행, 기준금리 동결", url="https://example.com/2", source="B"),
            ArticleCandidate(title="국제유가 상승", url="https://example.com/3", source="C"),
        ]
        deduped = dedupe_candidates(candidates, 0.9)
        self.assertEqual(len(deduped), 2)

    def test_wrap_text_caps_lines(self):
        lines = wrap_text(" ".join(["경제뉴스"] * 20), width=8, max_lines=3)
        self.assertLessEqual(len(lines), 3)
        self.assertTrue(lines[-1].endswith("…"))

    def test_validate_payload_normalizes_lines(self):
        items = _validate_payload(
            [
                {
                    "rank": 4,
                    "headline": "매우 긴 헤드라인입니다 " * 5,
                    "source": "테스트",
                    "url": "https://example.com",
                    "summary": "- 첫 줄입니다\n2년 만에 늘었습니다\n- 셋째 줄입니다\n- 넷째 줄입니다",
                    "points": ["1. 첫 포인트", "2. 둘째 포인트", "3. 셋째 포인트"],
                    "comment": "첫 코멘트\n둘째 코멘트\n셋째 코멘트",
                }
            ]
        )
        self.assertEqual(items[0].rank, 1)
        self.assertEqual(len(items[0].summary.splitlines()), 3)
        self.assertIn("2년", items[0].summary)
        self.assertEqual(len(items[0].comment.splitlines()), 3)
        self.assertEqual(items[0].points[0], "첫 포인트")

    def test_limit_by_source_balances_candidates(self):
        candidates = [
            ArticleCandidate(title=f"A{i}", url=f"https://a/{i}", source="A")
            for i in range(5)
        ] + [
            ArticleCandidate(title=f"B{i}", url=f"https://b/{i}", source="B")
            for i in range(2)
        ]
        limited = _limit_by_source(candidates, max_total=5, max_per_source=2)
        self.assertEqual([item.source for item in limited[:4]], ["A", "A", "B", "B"])
        self.assertEqual(len(limited), 5)

    def test_relevance_filter_skips_obvious_non_economy_articles(self):
        society = ArticleCandidate(
            title="마이클 잭슨, 英 오피셜 차트 점령",
            url="https://www.mk.co.kr/news/culture/1",
            source="매일경제 증권",
        )
        market = ArticleCandidate(
            title="국제유가 상승에 에너지 비용 부담 확대",
            url="https://www.example.com/world/energy",
            source="CNBC Economy",
        )
        self.assertFalse(_is_relevant_candidate(society))
        self.assertTrue(_is_relevant_candidate(market))

    def test_publish_guard_detects_fallback_cards(self):
        processed = process_articles(
            [ArticleCandidate(title="금리 뉴스", url="https://example.com", source="A", summary="금리 뉴스입니다.")],
            {"news_count": 1, "use_ai": False},
            force_fallback=True,
        )
        self.assertTrue(_looks_like_fallback(processed))


if __name__ == "__main__":
    unittest.main()
