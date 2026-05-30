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

`Daily Economic News` 워크플로를 선택한 뒤 `Run workflow`를 눌러 수동 실행할 수 있습니다.

현재 자동 실행 시간은 한국시간 매일 06:45입니다.

워크플로는 아래 순서로 실행됩니다.

1. 의존성 설치
2. 테스트 실행
3. RSS/텔레그램 preflight 점검
4. Gemini 요약 및 카드 생성
5. 텔레그램 채널 발송

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
