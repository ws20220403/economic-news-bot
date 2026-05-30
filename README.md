# 경제야 뭐했니 자동 발송 봇

매일 경제뉴스 후보를 모아 오늘의 경제 이슈 6개로 묶고, 각 이슈를 5장짜리 카드뉴스 앨범으로 만들어 텔레그램 채널에 발송하는 Python 프로젝트입니다.

## 현재 구조

- RSS 후보 수집 후 비경제성 기사 1차 필터링
- Gemini로 오늘의 경제 이슈 6개 선별
- 유사한 기사들은 하나의 이슈로 묶고, 이슈별 복수 출처 캡션 생성
- 카드 구성: 표지, 쉬운 요약, 핵심 포인트, 투자자 관점, 원문 보기
- Pretendard 기반 PNG 카드 생성
- Gemini 실패 시 실제 발송 중단, dry-run에서만 fallback 허용
- Telegram `sendMediaGroup`으로 이슈별 5장 앨범 발송

## 로컬 실행

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.main --dry-run
```

샘플 기사와 fallback 요약으로 디자인만 확인:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.main --sample --dry-run --fallback-ai
```

실제 텔레그램 발송:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.main
```

사전 점검:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.preflight --skip-gemini
```

테스트, 사전 점검, 실제 발송을 한 번에 실행:

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

`getUpdates` 충돌을 확인하려면:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.telegram_setup --get-updates
```

webhook을 삭제하고 대기 중 업데이트를 비운 뒤 다시 확인하려면:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python -m economic_news_bot.telegram_setup --drop-webhook --get-updates
```

## GitHub Actions

`.github/workflows/daily.yml`은 매일 한국시간 06:45에 실행됩니다.

GitHub 저장소의 Settings > Secrets and variables > Actions에 아래 4개를 등록해야 합니다.

- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `TELEGRAM_ADMIN_CHAT_ID`

워크플로는 발송 전에 테스트를 실행합니다. 테스트 실패 또는 Gemini 실패로 fallback 카드가 생성되는 경우 실제 발송은 중단됩니다.

## 품질 확인

생성 결과는 `output/rank_01`부터 `output/rank_06`까지 저장됩니다. 각 폴더에는 아래 파일이 생성됩니다.

- `01_cover.png`
- `02_summary.png`
- `03_points.png`
- `04_investor.png`
- `05_sources.png`

전체 처리 결과 텍스트는 `output/processed_news.json`에서 확인할 수 있습니다.
