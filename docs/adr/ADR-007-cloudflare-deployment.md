# ADR-007: Cloudflare Named Tunnel + Access 운영 배포 정책

## Status

Accepted (2026-06-17)

## Context

KOSPI-WATCHER는 실거래 자격증명(KIS/Kiwoom 키, 계좌번호), Anthropic 키, DART/ECOS/Naver 키 등 고가치 비밀과 금융 의사결정 권한을 다룬다. 운영 단계에서 이 시스템을 공개 인터넷에 그대로 노출하면, 포트 스캔·무인증 접근·자격증명 탈취 위험이 커진다. 특히 Execution Gateway는 향후 실주문 경로이므로 접근을 극도로 제한해야 한다.

스펙 §4(권장 기술 스택)는 Deployment로 Docker Compose, 운영 단계 고정 도메인, Cloudflare Named Tunnel, Cloudflare Access, Secret Manager(또는 준하는 보안 저장소)를 명시한다. 스펙 §14는 서비스 간 권한 최소화(원칙 9)와 Agent Service·Execution Gateway의 네트워크 수준 분리 가능성(원칙 10)을 요구한다.

다만 이번 Phase(0/1)는 로컬 개발·문서·스캐폴딩 범위이며, 이 장비엔 Docker가 없어 compose는 작성만 하고 실행/검증하지 않는다(오버레이 C). 따라서 본 ADR은 운영 배포 정책을 결정으로 기록하되, 즉시 구현하지는 않는다.

## Decision

운영 배포는 **Cloudflare Named Tunnel + Cloudflare Access**를 통해서만 외부에 노출하고, 인바운드 포트를 직접 개방하지 않는다.

1. **Named Tunnel.** 운영 단계에서 서비스는 Cloudflare Named Tunnel(`cloudflared`)을 통해 고정 도메인으로 노출한다. 원서버의 인바운드 포트를 공개 인터넷에 직접 열지 않으며, 모든 외부 트래픽은 Cloudflare 엣지를 경유한다.
2. **Cloudflare Access.** 관리자/운영 화면 등 민감 경로는 Cloudflare Access(아이덴티티 기반 인증)로 보호한다. 인증되지 않은 요청은 애플리케이션에 도달하기 전에 차단한다.
3. **서비스별 노출 차등.** Web/API 등 사용자 대면 경로와, Execution Gateway 같은 내부·고위험 경로의 노출 정책을 분리한다. Execution Gateway는 Agent Service에서도 네트워크 수준으로 분리 가능하게 두고(스펙 §14-10), 외부에 직접 노출하지 않는다.
4. **시크릿 분리.** 운영 비밀은 Secret Manager(또는 준하는 보안 저장소)에 둔다. `.env`는 Git에 포함하지 않고 `.env.example`엔 변수명만 둔다(스펙 §14). production secret을 Claude Code가 읽거나 출력하지 못한다는 운영 원칙을 문서화한다.
5. **이번 Phase 범위.** `infra/cloudflare`에 구성 자리(placeholder)와 문서만 둔다. Docker 미설치 장비이므로 compose·터널은 실행/검증하지 않고 보고서에 미검증으로 명시한다(오버레이 C).

## Consequences

- 원서버 포트를 직접 열지 않으므로 공격 표면이 크게 줄고, DDoS·스캔이 Cloudflare 엣지에서 1차 흡수된다.
- Access로 민감 경로에 아이덴티티 인증을 강제해, 무인증 접근·내부 화면 노출 위험을 낮춘다.
- Cloudflare에 대한 운영 의존이 생긴다(벤더 종속, Cloudflare 장애 시 영향). 고정 도메인·터널 구성·인증 정책을 운영 절차로 관리해야 한다(RUNBOOK 연계).
- 이번 Phase에선 미구현/미검증이므로, 운영 전 별도 단계에서 터널·Access·시크릿 저장소를 실제 구성·검증해야 한다.

## Alternatives Considered

- **직접 포트 개방 + Nginx/리버스 프록시(rejected).** 원서버에 포트를 열고 프록시로 보호. 구성은 익숙하나 인바운드가 직접 노출되고, 엣지 보호·아이덴티티 인증을 자체 구축해야 한다. 스펙이 Cloudflare Named Tunnel/Access를 명시하므로 기각.
- **VPN(WireGuard 등) 전용 접근(considered, not chosen).** 운영 화면을 VPN 뒤에만 둠. 강력하나 사용자 대면 웹에는 부적합하고 클라이언트 배포·키 관리 부담이 있다. 민감 경로엔 Access가, 사용자 경로엔 터널이 더 적합하여 채택하지 않았다.
- **관리형 PaaS 배포(considered, not chosen).** 클라우드 PaaS에 통째로 올림. 운영이 단순하나, 서비스 격리(Execution Gateway 분리)·시크릿 통제·고정 도메인+엣지 인증 요구를 스펙대로 충족하기엔 제약이 있어 이번 결정에선 채택하지 않았다. Docker Compose + Cloudflare 조합을 기본으로 둔다.
