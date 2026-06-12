# GitHub 배포 및 공유 안내

이 문서는 PC가 꺼져 있어도 매일 자동 발송되도록 GitHub Actions에 올리는 절차와, 주변 사람에게 결과물을 공유하는 방법을 정리합니다.

## 1. GitHub 저장소 만들기

1. GitHub에 로그인합니다.
2. 우측 상단 `+` 버튼에서 `New repository`를 선택합니다.
3. Repository name은 예를 들어 `economic-news-bot`으로 입력합니다.
4. 공개 여부를 선택합니다.
   - `Private`: 코드와 설정을 나만 볼 수 있습니다. 추천합니다.
   - `Public`: 누구나 코드를 볼 수 있습니다. 단, Secrets는 노출되지 않습니다.
5. `Add a README file`, `.gitignore`, `license`는 체크하지 않습니다.
6. `Create repository`를 누릅니다.

## 2. 로컬 코드를 GitHub에 올리기

GitHub 저장소를 만든 뒤, 저장소 페이지에 표시되는 HTTPS 주소를 복사합니다.

예시:

```powershell
git remote add origin https://github.com/YOUR_ID/economic-news-bot.git
git push -u origin main
```

이미 `origin`이 있다는 오류가 나면 아래처럼 바꿉니다.

```powershell
git remote set-url origin https://github.com/YOUR_ID/economic-news-bot.git
git push -u origin main
```

## 3. GitHub Secrets 등록

저장소 페이지에서 아래 메뉴로 이동합니다.

`Settings` > `Secrets and variables` > `Actions` > `New repository secret`

아래 4개를 각각 등록합니다.

```text
GEMINI_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHANNEL_ID
TELEGRAM_ADMIN_CHAT_ID
```

주의:

- `.env` 파일 내용은 GitHub에 올리지 않습니다.
- 값 앞뒤에 따옴표를 붙이지 않습니다.
- `TELEGRAM_CHANNEL_ID`는 `-100...` 형태일 수 있습니다.

## 4. 자동 실행 확인

저장소의 `Actions` 탭으로 이동합니다.

`Daily Economic News` 워크플로를 선택한 뒤 `Run workflow`를 눌러 수동 실행할 수 있습니다. (`dry_run`을 `true`로 두면 발송 없이 점검만 합니다.)

자동 실행은 한국시간 **06:42~07:51** 사이의 여러 특정 시각(목표 06:45)에 시도하며, 가장 먼저 가드를 통과한 실행이 그날 한 번만 발송합니다. GitHub은 `*/5`(5분마다) 같은 고빈도 크론을 하루 몇 번만 실행하도록 강하게 억제하므로, 혼잡한 정각(:00)을 피한 소수의 특정 시각으로 등록했습니다. (하루 한 번만 발송하도록 성공 시 그날 표식을 남깁니다.)

> 정시성을 100%로 보장하려면 외부 스케줄러(예: cron-job.org)가 매일 06:45에 GitHub `repository_dispatch`(event_type `daily-publish`)를 호출하게 붙이면 됩니다. 워크플로는 이미 이 트리거를 받도록 준비돼 있습니다.

워크플로는 아래 순서로 실행됩니다.

1. 발송 시간/중복 가드 확인
2. 의존성 설치
3. 테스트 실행
4. RSS/텔레그램 preflight 점검
5. Gemini 요약 및 카드 생성
6. 텔레그램 채널 발송

Gemini가 실패해 fallback 카드가 만들어지면 실제 발송은 중단됩니다.

## 5. 주변 사람에게 공유하는 방법

가장 쉬운 방법은 텔레그램 채널 초대 링크를 공유하는 것입니다.

텔레그램 앱에서:

1. 채널 `경제야 뭐했니`로 들어갑니다.
2. 채널 이름을 누릅니다.
3. `Subscribers` 또는 `Invite Links` 메뉴를 엽니다.
4. 초대 링크를 만들거나 복사합니다.
5. 주변 사람에게 링크를 보냅니다.

채널을 공개 채널로 운영하려면:

1. 채널 정보로 들어갑니다.
2. `Edit` 또는 연필 아이콘을 누릅니다.
3. `Channel Type`에서 Public Channel을 선택합니다.
4. 공개 주소를 설정합니다.

Private 채널은 초대 링크가 있는 사람만 들어올 수 있어 초기 운영에 더 적합합니다.

## 6. 코드를 공유하는 방법

코드까지 공유하려면 GitHub 저장소 주소를 공유하면 됩니다.

- Private 저장소: GitHub에서 Collaborator로 초대해야 볼 수 있습니다.
- Public 저장소: 링크만 있으면 누구나 볼 수 있습니다.

민감한 값은 Secrets에만 저장되므로 GitHub 저장소를 공유해도 API 키와 텔레그램 토큰은 보이지 않습니다.
