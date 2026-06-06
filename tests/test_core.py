import unittest

from economic_news_bot.ai_processor import _validate_payload, process_articles
from economic_news_bot.card_builder import wrap_text
from economic_news_bot.main import _looks_like_fallback
from economic_news_bot.models import ArticleCandidate, ProcessedNews
from economic_news_bot.quality import validate_processed_news
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
        summary_lines = [
            "첫 문장은 기준금리와 환율 움직임이 동시에 나타난 배경을 독자가 이해할 수 있도록 완결된 설명으로 정리합니다.",
            "둘째 문장은 2년 만에 늘어난 지표 변화가 가계와 기업 비용에 어떤 압력을 주는지 구체적으로 설명합니다.",
            "셋째 문장은 정책 당국과 시장 참가자가 다음 발표에서 확인해야 할 변수를 빠짐없이 짚어 줍니다.",
        ]
        point_lines = [
            "첫 포인트는 금리와 환율이 함께 움직일 때 수입 물가와 소비 심리에 미치는 영향을 연결해서 설명합니다.",
            "둘째 포인트는 기업 조달 비용과 실적 전망이 업종별로 달라질 수 있다는 점을 구체적으로 짚습니다.",
            "셋째 포인트는 다음 통계 발표와 중앙은행 발언을 함께 확인해야 한다는 점을 투자자 관점에서 정리합니다.",
        ]
        comment_lines = [
            "첫 코멘트는 단기 가격 반응보다 지표 변화가 이어지는지 확인해야 한다는 방향으로 정리합니다.",
            "둘째 코멘트는 관련 업종의 비용 부담과 매출 민감도를 나누어 봐야 한다는 점을 설명합니다.",
            "셋째 코멘트는 매수나 매도 결론보다 변동성 관리와 원문 수치 확인이 우선이라는 점을 강조합니다.",
        ]
        items = _validate_payload(
            [
                {
                    "rank": 4,
                    "headline": "매우 긴 헤드라인입니다 " * 5,
                    "source": "테스트",
                    "url": "https://example.com",
                    "summary": "\n".join(summary_lines),
                    "points": point_lines,
                    "comment": "\n".join(comment_lines),
                    "one_sentence": "금리와 환율 변화가 생활비와 기업 비용에 미치는 영향을 한 번에 짚어야 하는 상황입니다.",
                }
            ]
        )
        self.assertEqual(items[0].rank, 1)
        self.assertEqual(len(items[0].summary.splitlines()), 3)
        self.assertIn("2년", items[0].summary)
        self.assertEqual(len(items[0].comment.splitlines()), 3)
        self.assertEqual(items[0].points[0], point_lines[0])

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

    def test_quality_guard_rejects_truncated_sentence(self):
        good_sentence = "이 문장은 주요 수치와 시장 반응을 함께 설명해 독자가 흐름을 놓치지 않도록 완결된 문장으로 정리합니다."
        item = ProcessedNews(
            rank=1,
            headline="테스트 헤드라인",
            source="테스트",
            url="https://example.com",
            summary="\n".join([good_sentence, good_sentence, good_sentence]),
            points=[good_sentence, good_sentence, good_sentence],
            comment="\n".join([good_sentence, good_sentence, good_sentence.replace("정리합니다.", "정리...")]),
            one_sentence="오늘 경제 흐름은 금리와 환율, 기업 비용 변화를 함께 확인해야 하는 상황입니다.",
        )
        with self.assertRaises(ValueError):
            validate_processed_news([item], {"validate_card_layout": False})


if __name__ == "__main__":
    unittest.main()
