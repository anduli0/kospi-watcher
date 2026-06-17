# ADR-021: 08:00 Asia/Seoul 아침 브리핑 → Telegram 자동 전송

## Status

Accepted (2026-06-17)

## Context

예측 리포트(ADR-017)와 뉴스 데일리 브리프(ADR-020)가 갖춰지자, 이용자가 매일 아침 웹을 열거나 API를 수동 호출하지 않아도 **오늘의 예보 + 뉴스 요약을 알아서 받아보는** 푸시 경로가 필요해졌다. 자매 시스템(Fed-Watcher/KRW-Watcher)도 텔레그램 데일리 브리프를 핵심 UX로 둔다.

요구사항은 다음과 같다: (1) 정해진 시각(한국 장 시작 전, 08:00 Asia/Seoul)에 자동 실행; (2) 한 번의 작업으로 **스크랩 → 예측 생성·저장 → 뉴스 브리프 생성·저장 → 전송**까지 일괄 처리; (3) 봇 토큰 등 비밀이 미설정이어도 데이터 갱신은 막히지 않고 안전히 동작; (4) 비밀(`TELEGRAM_BOT_TOKEN`)은 절대 로그에 남지 않을 것; (5) 봇 토큰 없이도 메시지 렌더링을 확인할 수 있는 수동 트리거 제공.

기존 worker(ADR-012, APScheduler)는 이미 `heartbeat`/`scrape_news` 잡을 돌린다. 여기에 시각 기반(cron) 브리핑 잡과 Telegram 전송 계층을 더하되, 안전 불변식(예측은 결정론·디스플레이 전용, 주문 권한 없음, 비밀 비노출)을 그대로 유지해야 했다.

## Decision

**worker에 08:00 Asia/Seoul cron으로 도는 아침 브리핑 잡을 추가**하고, scrape→predict→brief→Telegram 파이프라인을 한 함수로 묶으며, never-raises·미설정-시-skip하는 Telegram 전송 계층과 수동 트리거 API를 둔다.

1. **08:00 Asia/Seoul cron 잡(worker).** `worker/scheduler.py`의 `build_scheduler`가 `morning_briefing` 잡을 `CronTrigger(hour=settings.morning_briefing_hour, minute=settings.morning_briefing_minute, timezone="Asia/Seoul")`로 등록한다(id `morning_briefing`, `replace_existing=True`). 스케줄러 인스턴스의 기준 tz는 `"UTC"`이지만, 이 잡의 트리거 자체가 **Asia/Seoul**이라 기본값 08:00은 한국시간 08:00에 발화한다(`morning_briefing_hour=8`, `morning_briefing_minute=0`). worker는 `scrape_news`(매 60분)와 `heartbeat`(매 60초)도 함께 돌린다.
2. **scrape → predict → brief → telegram 파이프라인.** `briefing/service.py`의 `run_morning_briefing(session)`이 한 트랜잭션 흐름으로: (a) `NewsService().scrape` — 뉴스 스크랩·정리(ADR-018); (b) `repositories.recent_headlines`로 최근 헤드라인을 받아 `PredictionService().generate(...)`로 예측을 만들고 `repositories.save_prediction`으로 저장(ADR-017); (c) `NewsService().generate_daily_brief`로 뉴스 브리프 생성·저장(ADR-020); (d) `format_report_message`/`format_brief_message`로 **두 개의 Telegram 메시지**(예측 리포트 / 뉴스 브리프, HTML 파싱·`html.escape`)를 렌더링; (e) `send_telegram_message`로 각각 전송. 결과는 `BriefingResult`(뉴스 추가 건수·예측 방향·브리프 건수·렌더된 두 메시지·각 전송 상태·`telegram_enabled`)로 반환한다.
3. **never-raises · 미설정 시 skip하는 Telegram 전송.** `infrastructure/telegram.py`의 `send_telegram_message`는 Bot API `sendMessage`(`https://api.telegram.org/bot<token>/sendMessage`, `disable_web_page_preview=True`)를 호출하는 **전송 전용** 계층이다. `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`가 비어 있으면 호출하지 않고 `TelegramResult(ok=False, "telegram not configured …")`를 반환한다. `httpx.HTTPError`나 비-200 응답에서도 **예외를 던지지 않고** `ok=False`와 사유 문자열만 돌려준다. 따라서 봇 토큰이 없거나 텔레그램이 불통이어도 "데이터는 갱신되되 전송만 건너뛴다". 토큰은 `get_secret_value()`로만 읽어 URL에 쓰며 **로그·응답 어디에도 남기지 않는다**.
4. **비밀은 SecretStr, 로그 금지.** 설정(`config.py`)에 `telegram_bot_token: SecretStr`, `telegram_chat_id: str`, `morning_briefing_hour: int = 8`, `morning_briefing_minute: int = 0`을 둔다. 토큰은 `SecretStr`이라 실수로 직렬화·출력되지 않고(ADR-006 구조적 로깅의 비밀 마스킹과 일관), 응답 스키마에도 노출하지 않는다. `Settings.telegram_enabled` 프로퍼티(`bool(token and chat_id)`)로 구성 여부를 정직히 판별한다.
5. **수동 트리거 API.** `api/routes/notify.py`의 `POST /api/v1/notify/morning`이 cron과 **동일한 `run_morning_briefing`** 파이프라인을 즉시 실행하고, 렌더된 두 메시지와 Telegram 전송 상태(`MorningBriefingResponse`)를 반환한다. 봇 토큰 없이도 메시지 미리보기·테스트가 가능하다.
6. **전송에는 worker 프로세스가 떠 있어야 함.** 자동 전송은 worker(`apps/worker/main.py`)가 실행 중일 때만 일어난다. API/web만 띄운 경우 08:00 자동 전송은 발생하지 않으며, 그때는 `POST /api/v1/notify/morning`으로 수동 실행해야 한다.

## Consequences

- 이용자는 매일 아침 08:00(한국시간)에 **예측 리포트 + 뉴스 브리프**를 텔레그램으로 자동 수신한다(웹 접속·수동 호출 불필요). 한 잡이 데이터 갱신과 전송을 함께 처리해 "오늘" 화면도 동시에 최신화된다.
- Telegram 계층이 never-raises·미설정-skip이라, 봇 토큰이 없거나 텔레그램이 불통이어도 브리핑 잡은 실패하지 않는다(데이터는 갱신, 전송만 생략). 운영 진입 장벽이 낮다.
- 비밀이 `SecretStr`이고 로그·응답에 노출되지 않아, 토큰 유출 위험이 통제된다. `telegram_enabled` 프로퍼티로 구성 여부를 정직히 보고한다.
- 자동 전송은 **worker 프로세스 가동이 전제**다. 무도커 로컬모드(ADR-012)에서 worker를 별도로 띄우지 않으면 08:00 푸시가 없으므로, 이를 RUNBOOK/CLAUDE.md에 명시한다. 그 경우 `POST /api/v1/notify/morning`이 대안 경로다.
- 예측·브리프 생성 로직은 그대로(결정론·디스플레이 전용·주문 권한 없음)라, 푸시 경로 추가가 트레이딩 안전 불변식을 건드리지 않는다.

## Alternatives Considered

- **API 프로세스 내 스케줄러(rejected).** API에 cron을 붙이면 worker 없이도 돌지만, 시각 기반 백그라운드 작업은 worker의 책임(ADR-012)이고 API 다중 워커 환경에서 중복 발화 위험이 있다. 브리핑은 worker의 단일 cron 잡으로 둔다.
- **OS 크론/작업 스케줄러로 외부 트리거(considered, not chosen).** 플랫폼 의존적이고 APScheduler 기반 worker와 이원화된다. 이미 있는 worker에 cron 잡을 더하는 편이 일관적이다.
- **전송 실패 시 예외 전파/재시도(considered, not chosen).** 전송 실패로 브리핑 잡 전체를 깨뜨리면 데이터 갱신까지 막힌다. 전송은 best-effort(never-raises, 상태만 반환)로 두고, 미설정/불통을 정직히 보고한다.
- **이메일·웹푸시 등 다른 전송 채널(considered, not chosen).** 자매 시스템과의 일관성·도입 단순성(키리스에 가까운 봇 토큰 하나)을 위해 Telegram으로 시작한다. 전송 계층이 분리돼 있어 후속 채널 추가 여지는 남는다.
