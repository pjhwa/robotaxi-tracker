# Web Push 알림 설계 — Robotaxi Tracker

**날짜:** 2026-06-09  
**상태:** Implemented  
**범위:** Tesla 차량 대수 변경 시 iPhone PWA로 Web Push 알림 전송

> **현행 (2026-08-08):** HTTPS 대시보드 포트 **8443**, VAPID 키(`.env` + `vapid/private_key.pem`).  
> 스크랩이 실패하면 `notify_if_changed`는 호출되지 않는다. 수집 실패 자체는 Web Push가 아니라  
> `/health` + UI 경고 배너로 표시한다. 운영 요약은 [README](../../../README.md), [DATA_SOURCE](../../DATA_SOURCE.md).

---

## 목표

Tesla 차량 대수가 변경될 때 홈화면에 추가된 iPhone PWA에 Web Push 알림을 전송한다.
알림 형식: "Tesla 차량 5대 증가 (215 → 220)"

---

## 전제 조건

- iOS 16.4+ 필요 (Web Push for Home Screen PWA 지원 버전)
- Web Push는 HTTPS 필수 → Tailscale cert 활용
- 현재 접속 URL: `http://jerrymacmini.tailxxxx.ts.net:8080`
- 변경 후 URL: `https://jerrymacmini.tailxxxx.ts.net:8443`
- 홈화면 PWA 재등록 필요 (HTTPS URL로)

---

## 아키텍처

```
[iPhone PWA]
     │  ① 알림 허용 → subscription 정보 전송
     ▼
[API (FastAPI)]
     │  ② subscription을 SQLite에 저장
     ▼
[SQLite DB] ←── [Scraper]
                    │  ③ 15분마다 Tesla 차량수 비교
                    │  변경 감지 시
                    ▼
             [pywebpush 라이브러리]
                    │  ④ VAPID으로 Apple Push 서버에 전송
                    ▼
             [Apple Push Service]
                    │  ⑤ 아이폰으로 알림 전달
                    ▼
             [iPhone 알림: "Tesla 차량 5대 증가 (215 → 220)"]
```

---

## 컴포넌트별 변경사항

### 1. HTTPS 설정 (1회성)

Mac에서 Tailscale cert 발급:
```bash
tailscale cert jerrymacmini.tailxxxx.ts.net
```
생성 파일: `jerrymacmini.tailxxxx.ts.net.crt`, `jerrymacmini.tailxxxx.ts.net.key`

cert 파일 위치: `./certs/` 디렉토리에 저장, Docker bind mount로 nginx에 전달.

nginx 포트: 8080(HTTP) → 8443(HTTPS)

### 2. SQLite DB — 새 테이블

```sql
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT UNIQUE NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

### 3. API (FastAPI)

새 엔드포인트 3개:

| Method | Path | 설명 |
|--------|------|------|
| GET | `/push/vapid-public-key` | VAPID 공개키 반환 |
| POST | `/push/subscribe` | 구독 정보 저장 |
| DELETE | `/push/unsubscribe` | 구독 삭제 |

POST `/push/subscribe` 요청 body:
```json
{
  "endpoint": "https://web.push.apple.com/...",
  "keys": {
    "p256dh": "...",
    "auth": "..."
  }
}
```

환경변수 추가:
- `VAPID_PRIVATE_KEY`
- `VAPID_PUBLIC_KEY`
- `VAPID_CLAIM_EMAIL`

### 4. Scraper — 변경 감지 + Push 전송

`run_scrape()` 완료 후 실행되는 `notify_if_changed()` 함수 추가:

```
1. DB에서 Tesla(permit=AV8313426653583)의 최근 snapshot 2개 조회
2. vehicle_count 비교
3. 다르면:
   - 증감 방향 계산 (증가/감소, N대)
   - push_subscriptions 전체 조회
   - 각 subscription에 pywebpush로 전송
   - 만료된 subscription(410 응답)은 자동 삭제
4. 같으면: 아무것도 하지 않음
```

알림 payload:
```json
{
  "title": "Tesla Robotaxi 업데이트",
  "body": "Tesla 차량 5대 증가 (215 → 220)"
}
```

pywebpush를 `scraper/requirements.txt`에 추가.

### 5. Frontend (React)

**Service Worker** (`frontend/public/sw.js`):
```js
self.addEventListener('push', event => {
  const { title, body } = event.data.json();
  event.waitUntil(
    self.registration.showNotification(title, { body, icon: '/favicon.svg' })
  );
});
```

**Web App Manifest** (`frontend/public/manifest.json`): PWA 메타데이터 (name, icons, display: standalone).

**알림 버튼**: `Header` 컴포넌트에 추가.
- 미구독: "알림 받기" 버튼
- 구독 중: "알림 끄기" 버튼
- 클릭 시 브라우저 알림 권한 요청 → VAPID 공개키로 subscribe → API POST

### 6. docker-compose.yml 변경

```yaml
frontend:
  ports:
    - "8443:443"        # HTTPS (기존 8080:80 대체)
  volumes:
    - ./certs:/etc/nginx/certs:ro

api:
  environment:
    - VAPID_PRIVATE_KEY=${VAPID_PRIVATE_KEY}
    - VAPID_PUBLIC_KEY=${VAPID_PUBLIC_KEY}
    - VAPID_CLAIM_EMAIL=${VAPID_CLAIM_EMAIL}

scraper:
  environment:
    - VAPID_PRIVATE_KEY=${VAPID_PRIVATE_KEY}
    - VAPID_PUBLIC_KEY=${VAPID_PUBLIC_KEY}
    - VAPID_CLAIM_EMAIL=${VAPID_CLAIM_EMAIL}
```

VAPID 키는 `.env` 파일로 관리 (`.gitignore`에 추가).

---

## 파일 변경 목록

| 파일 | 변경 유형 |
|------|----------|
| `scraper/main.py` | 수정 — `notify_if_changed()` 추가 |
| `scraper/db.py` | 수정 — push_subscriptions CRUD 추가 |
| `scraper/requirements.txt` | 수정 — pywebpush 추가 |
| `api/main.py` | 수정 — push 엔드포인트 3개 추가 |
| `api/api_db.py` | 수정 — push_subscriptions CRUD 추가 |
| `api/models.py` | 수정 — PushSubscription 모델 추가 |
| `scraper/db.py` | 수정 — init_db에 push_subscriptions 테이블 추가 |
| `frontend/public/sw.js` | 신규 — Service Worker |
| `frontend/public/manifest.json` | 신규 — PWA manifest |
| `frontend/index.html` | 수정 — manifest 링크 추가 |
| `frontend/src/components/Header.jsx` | 수정 — 알림 구독 버튼 추가 |
| `frontend/src/api.js` | 수정 — push API 호출 함수 추가 |
| `frontend/nginx.conf` | 수정 — HTTPS + cert 설정 |
| `docker-compose.yml` | 수정 — 포트/볼륨/환경변수 |
| `.env.example` | 신규 — VAPID 키 템플릿 |
| `.gitignore` | 수정 — .env, certs/ 추가 |

---

## 사용자 흐름

1. Mac에서 `tailscale cert` 실행 → `certs/` 디렉토리에 저장
2. VAPID 키 생성 → `.env` 파일 작성
3. `docker-compose up --build` 재실행
4. 아이폰 Safari에서 `https://jerrymacmini.tailxxxx.ts.net:8443` 접속
5. "홈화면에 추가"
6. 앱 열고 "알림 받기" 버튼 탭 → 권한 허용
7. Tesla 차량 대수 변경 시 자동 알림 수신

---

## 범위 외

- 다른 운영사 알림 (Tesla만)
- 알림 히스토리 저장
- 알림 필터 설정 UI
- 여러 사용자 구독 관리 UI
