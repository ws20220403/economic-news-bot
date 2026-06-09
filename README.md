# 경제야 뭐했니 자동 발송 봇

매일 아침 경제뉴스 후보를 모아 오늘의 경제 이슈 6개로 묶고, 각 이슈를 5장짜리 카드뉴스 앨범으로 만들어 텔레그램 채널에 발송하는 Python 프로젝트입니다.

## 동작 개요

1. RSS 후보 수집 후 비경제 기사 1차 필터링·중복 제거
2. Gemini가 오늘의 경제 이슈 6개를 선별하고, 이슈별로 요약·핵심 포인트·투자자 관점·복수 출처를 작성
3. 요약/포인트/코멘트는 **정확히 3문장**으로 정규화하고, 카드에 실제로 들어갈 크기를 픽셀 단위로 검증해 잘림을 방지
4. 밝고 깔끔한 카드 5장 생성: 표지 → 쉬운 요약 → 핵심 포인트 → 투자자 관점 → 원문 출처
5. Telegram `sendMediaGroup`으로 이슈별 앨범 발송 (실패 시 재시도)

Gemini 처리가 끝내 실패하면 실제 발송은 중단되고, `--dry-run`에서만 점검용 fallback 카드가 생성됩니다.

## 로컬 실행

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.main --dry-run
```

샘플 기사 + 점검용 요약으로 디자인만 확인:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.main --sample --dry-run --fallback-ai
```

실제 텔레그램 발송:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.main
```

사전 점검(테스트 → preflight → 발송)을 한 번에:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1
```

## 필요한 환경 변수

운영 발송에는 아래 값이 필요합니다. 실제 키는 `.env` 또는 GitHub Actions Secrets에 넣고, 채팅이나 저장소에 노출하지 않습니다.

```text
GEMINI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNEL_ID=
TELEGRAM_ADMIN_CHAT_ID=
```

## Telegram 설정 점검

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.telegram_setup
```

webhook을 삭제하고 대기 업데이트를 비운 뒤 다시 확인:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.telegram_setup --drop-webhook --get-updates
```

## 자동 발송 (GitHub Actions)

`.github/workflows/daily.yml`은 한국시간 **06:40~07:50** 구간에 5분 간격으로 점검 실행되며,
가장 먼저 가드를 통과한 실행이 그날 한 번만 발송합니다. (GitHub 스케줄러의 지연을 고려해 목표 시각 06:45 부근에 여러 번 시도)

저장소 `Settings > Secrets and variables > Actions`에 아래 4개를 등록해야 합니다.

- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `TELEGRAM_ADMIN_CHAT_ID`

워크플로는 발송 전에 테스트와 preflight를 실행하며, Gemini 실패로 fallback 카드가 만들어지면 발송을 중단합니다.

자세한 저장소 생성·Secrets 등록·공유 방법은 [docs/github_setup.md](docs/github_setup.md)를 참고하세요.

## 설정 (`config.json`)

- `news_count`: 발송할 이슈 수 (기본 6)
- `model`: Gemini 모델 (기본 `gemini-2.5-flash`)
- `gemini_attempts` / `gemini_timeout_seconds`: 재시도 횟수·타임아웃
- `telegram_album_delay_seconds`: 앨범 간 발송 간격
- `rss_sources`: 수집 대상 RSS 목록 (`enabled`로 on/off)

## 결과물

생성 결과는 `output/rank_01`부터 `output/rank_06`까지 저장됩니다.

- `01_cover.png` (표지)
- `02_summary.png` (쉬운 요약)
- `03_points.png` (핵심 포인트)
- `04_investor.png` (투자자 관점)
- `05_sources.png` (원문 출처)

전체 처리 결과 텍스트는 `output/processed_news.json`에서 확인할 수 있습니다.
