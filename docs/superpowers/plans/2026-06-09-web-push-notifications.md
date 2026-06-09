# Web Push 알림 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tesla 차량 대수가 변경될 때 iPhone PWA(홈화면 추가)에 "Tesla 차량 N대 증가/감소 (old → new)" 형식으로 Web Push 알림을 전송한다.

**Architecture:** 스크래퍼가 Tesla 차량 대수 변경을 감지하면 SQLite에 저장된 push 구독 정보로 pywebpush를 사용해 Apple Push 서버에 VAPID 서명된 알림을 전송한다. 프론트엔드는 Service Worker로 알림을 수신하고, Header에 구독/구독취소 버튼을 제공한다. Tailscale cert로 HTTPS를 구성한다.

**Tech Stack:** Python/FastAPI, pywebpush==1.14.1, cryptography, React/Vite, Service Worker API, Web Push API, Tailscale TLS cert, nginx SSL

---

## 파일 목록

| 파일 | 변경 유형 | 역할 |
|------|----------|------|
| `scraper/db.py` | 수정 | push_subscriptions 테이블 + CRUD |
| `scraper/main.py` | 수정 | notify_if_changed() 추가 |
| `scraper/requirements.txt` | 수정 | pywebpush 추가 |
| `scraper/test_db.py` | 수정 | push_subscriptions 테스트 |
| `api/api_db.py` | 수정 | push subscription CRUD |
| `api/models.py` | 수정 | PushSubscriptionRequest, UnsubscribeRequest |
| `api/main.py` | 수정 | /push/* 엔드포인트 3개 |
| `api/test_api.py` | 수정 | push 엔드포인트 테스트 |
| `frontend/public/sw.js` | 신규 | Service Worker (push 이벤트 수신) |
| `frontend/public/manifest.json` | 신규 | PWA manifest |
| `frontend/index.html` | 수정 | manifest + apple PWA 메타태그 |
| `frontend/src/api.js` | 수정 | push API 호출 함수 3개 |
| `frontend/src/components/Header.jsx` | 수정 | 알림 구독 버튼 |
| `frontend/src/components/Header.module.css` | 수정 | 버튼 스타일 |
| `frontend/nginx.conf` | 수정 | HTTPS + cert 설정 |
| `docker-compose.yml` | 수정 | 포트/볼륨/환경변수 |
| `scripts/gen_vapid_keys.py` | 신규 | VAPID 키 1회 생성 스크립트 |
| `.env.example` | 신규 | 환경변수 템플릿 |
| `.gitignore` | 수정 | vapid/, certs/ 추가 |

---

## Task 1: HTTPS 설정 (Tailscale cert + nginx + docker-compose)

**Files:**
- Modify: `frontend/nginx.conf`
- Modify: `docker-compose.yml`
- Create directory: `certs/` (gitignore됨)

> **사전 작업 (터미널에서 수동 실행):**
> ```bash
> # 프로젝트 루트에서 실행
> mkdir -p certs
> # YOUR_HOSTNAME을 실제 Tailscale 호스트명으로 교체
> tailscale cert --cert-file certs/YOUR_HOSTNAME.crt --key-file certs/YOUR_HOSTNAME.key YOUR_HOSTNAME
> ```
> 예: `tailscale cert --cert-file certs/jerrymacmini.tail1234.ts.net.crt --key-file certs/jerrymacmini.tail1234.ts.net.key jerrymacmini.tail1234.ts.net`

- [ ] **Step 1: .gitignore에 certs/, vapid/ 추가**

`/Users/jerry/dev/robotaxi-tracker/.gitignore`에 아래 두 줄 추가:
```
certs/
vapid/
```

- [ ] **Step 2: nginx.conf를 HTTPS로 교체**

`frontend/nginx.conf`를 아래로 교체 (YOUR_HOSTNAME은 실제 Tailscale 호스트명):
```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/certs/YOUR_HOSTNAME.crt;
    ssl_certificate_key /etc/nginx/certs/YOUR_HOSTNAME.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: docker-compose.yml 업데이트**

`docker-compose.yml`을 아래로 교체:
```yaml
services:
  scraper:
    build: ./scraper
    volumes:
      - robotaxi_db:/data
      - ./vapid:/vapid:ro
    environment:
      - DB_PATH=/data/robotaxi.db
      - VAPID_PRIVATE_KEY_PATH=/vapid/private_key.pem
      - VAPID_CLAIM_EMAIL=${VAPID_CLAIM_EMAIL}
    restart: unless-stopped
    depends_on: []

  api:
    build: ./api
    volumes:
      - robotaxi_db:/data
    environment:
      - DB_PATH=/data/robotaxi.db
      - VAPID_PUBLIC_KEY=${VAPID_PUBLIC_KEY}
    ports:
      - "8000:8000"
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "8443:443"
    volumes:
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  robotaxi_db:
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore frontend/nginx.conf docker-compose.yml
git commit -m "feat: configure HTTPS via Tailscale cert for Web Push"
```

---

## Task 2: VAPID 키 생성 스크립트 + .env 설정

**Files:**
- Create: `scripts/gen_vapid_keys.py`
- Create: `.env.example`
- Create (not committed): `vapid/private_key.pem`, `.env`

- [ ] **Step 1: scripts/ 디렉토리 생성 및 gen_vapid_keys.py 작성**

```bash
mkdir -p scripts
```

`scripts/gen_vapid_keys.py`:
```python
#!/usr/bin/env python3
"""One-time script to generate VAPID keys. Run once, save output to .env."""
import base64
import os
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

key = ec.generate_private_key(ec.SECP256R1())

pem = key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption(),
)

pub = key.public_key().public_bytes(
    serialization.Encoding.X962,
    serialization.PublicFormat.UncompressedPoint,
)
public_b64 = base64.urlsafe_b64encode(pub).rstrip(b"=").decode()

os.makedirs("vapid", exist_ok=True)
with open("vapid/private_key.pem", "wb") as f:
    f.write(pem)

print(f"VAPID_PUBLIC_KEY={public_b64}")
print("VAPID_CLAIM_EMAIL=inlinetoday@gmail.com")
print()
print("vapid/private_key.pem 저장 완료. 위 두 줄을 .env에 추가하세요.")
```

- [ ] **Step 2: .env.example 작성**

`.env.example`:
```
VAPID_PUBLIC_KEY=<base64url-encoded-public-key>
VAPID_CLAIM_EMAIL=inlinetoday@gmail.com
```

- [ ] **Step 3: VAPID 키 생성 실행 (수동)**

> 프로젝트 루트에서 실행. `cryptography` 라이브러리가 없으면 먼저 `pip install cryptography` 실행.

```bash
python3 scripts/gen_vapid_keys.py
```

출력 예시:
```
VAPID_PUBLIC_KEY=BGxxxxxxxxxxxxxxxx...
VAPID_CLAIM_EMAIL=inlinetoday@gmail.com

vapid/private_key.pem 저장 완료. 위 두 줄을 .env에 추가하세요.
```

출력된 두 줄을 `.env` 파일에 저장:
```bash
python3 scripts/gen_vapid_keys.py | head -2 > .env
```

- [ ] **Step 4: Commit**

```bash
git add scripts/gen_vapid_keys.py .env.example
git commit -m "feat: add VAPID key generation script"
```

---

## Task 3: DB — push_subscriptions 테이블 + CRUD

**Files:**
- Modify: `scraper/db.py`
- Modify: `scraper/test_db.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`scraper/test_db.py`에 아래 테스트 추가:
```python
from db import init_db, upsert_operator, insert_snapshot, \
    save_subscription, get_all_subscriptions, delete_subscription, \
    get_tesla_recent_snapshots

def test_push_subscriptions_table_created(db_path):
    import sqlite3
    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "push_subscriptions" in tables

def test_save_and_get_subscription(db_path):
    save_subscription(db_path, "https://push.example.com/1", "p256dh_val", "auth_val")
    subs = get_all_subscriptions(db_path)
    assert len(subs) == 1
    assert subs[0]["endpoint"] == "https://push.example.com/1"
    assert subs[0]["p256dh"] == "p256dh_val"
    assert subs[0]["auth"] == "auth_val"

def test_save_subscription_upserts(db_path):
    save_subscription(db_path, "https://push.example.com/1", "old_p256dh", "old_auth")
    save_subscription(db_path, "https://push.example.com/1", "new_p256dh", "new_auth")
    subs = get_all_subscriptions(db_path)
    assert len(subs) == 1
    assert subs[0]["p256dh"] == "new_p256dh"

def test_delete_subscription(db_path):
    save_subscription(db_path, "https://push.example.com/1", "p256dh_val", "auth_val")
    delete_subscription(db_path, "https://push.example.com/1")
    assert get_all_subscriptions(db_path) == []

def test_get_tesla_recent_snapshots(db_path):
    upsert_operator(db_path, "AV8313426653583", "Tesla", "AV8313426653583")
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    insert_snapshot(db_path, "AV8313426653583", 110, "Model Y", "Authorized", "{}")
    snaps = get_tesla_recent_snapshots(db_path, "AV8313426653583", limit=2)
    assert len(snaps) == 2
    assert snaps[0]["vehicle_count"] == 110
    assert snaps[1]["vehicle_count"] == 100
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/jerry/dev/robotaxi-tracker/scraper && python -m pytest test_db.py::test_push_subscriptions_table_created -v
```
Expected: `FAILED` (ImportError 또는 AssertionError)

- [ ] **Step 3: scraper/db.py 업데이트**

`scraper/db.py`의 `init_db` 함수에 push_subscriptions 테이블 추가 및 새 함수 4개 추가:

기존 `init_db` 내부 `conn.executescript("""...""")`의 마지막 `CREATE INDEX` 직후에 아래 추가:

```python
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
```

파일 맨 끝에 새 함수 4개 추가:
```python
def save_subscription(db_path: str, endpoint: str, p256dh: str, auth: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            INSERT OR REPLACE INTO push_subscriptions (endpoint, p256dh, auth, created_at)
            VALUES (?, ?, ?, ?)
        """, (endpoint, p256dh, auth, now))
        conn.commit()
    finally:
        conn.close()


def get_all_subscriptions(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT endpoint, p256dh, auth FROM push_subscriptions"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def delete_subscription(db_path: str, endpoint: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        )
        conn.commit()
    finally:
        conn.close()


def get_tesla_recent_snapshots(db_path: str, operator_id: str, limit: int = 2) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT vehicle_count, captured_at
            FROM snapshots
            WHERE operator_id = ?
            ORDER BY captured_at DESC
            LIMIT ?
        """, (operator_id, limit)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd /Users/jerry/dev/robotaxi-tracker/scraper && python -m pytest test_db.py -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper/db.py scraper/test_db.py
git commit -m "feat: add push_subscriptions table and CRUD to scraper db"
```

---

## Task 4: API — push 엔드포인트 3개

**Files:**
- Modify: `api/models.py`
- Modify: `api/api_db.py`
- Modify: `api/main.py`
- Modify: `api/test_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`api/test_api.py`에 아래 테스트 추가 (기존 import에 monkeypatch 이미 있음):
```python
def test_get_vapid_public_key(client, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "test_public_key_123")
    import importlib
    import main as app_module
    importlib.reload(app_module)
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.get("/push/vapid-public-key")
    assert r.status_code == 200
    assert r.json()["publicKey"] == "test_public_key_123"

def test_subscribe(client):
    payload = {
        "endpoint": "https://web.push.apple.com/test",
        "keys": {"p256dh": "p256dh_val", "auth": "auth_val"},
    }
    r = client.post("/push/subscribe", json=payload)
    assert r.status_code == 201
    assert r.json()["ok"] is True

def test_unsubscribe(client):
    client.post("/push/subscribe", json={
        "endpoint": "https://web.push.apple.com/test",
        "keys": {"p256dh": "p256dh_val", "auth": "auth_val"},
    })
    r = client.delete("/push/unsubscribe", json={"endpoint": "https://web.push.apple.com/test"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/jerry/dev/robotaxi-tracker/api && python -m pytest test_api.py::test_subscribe -v
```
Expected: `FAILED`

- [ ] **Step 3: api/models.py에 모델 추가**

`api/models.py` 파일 끝에 추가:
```python
class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: dict


class UnsubscribeRequest(BaseModel):
    endpoint: str
```

- [ ] **Step 4: api/api_db.py에 push CRUD 추가**

`api/api_db.py` 상단 import에 추가:
```python
from datetime import datetime, timezone
```

파일 끝에 함수 2개 추가:
```python
def save_push_subscription(db_path: str, endpoint: str, p256dh: str, auth: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn(db_path)
    try:
        conn.execute("""
            INSERT OR REPLACE INTO push_subscriptions (endpoint, p256dh, auth, created_at)
            VALUES (?, ?, ?, ?)
        """, (endpoint, p256dh, auth, now))
        conn.commit()
    finally:
        conn.close()


def delete_push_subscription(db_path: str, endpoint: str) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: api/main.py에 엔드포인트 추가**

`api/main.py`의 import에 추가:
```python
from models import OperatorSummary, SnapshotPoint, ChangeEvent, LatestSnapshot, HealthResponse, \
    PushSubscriptionRequest, UnsubscribeRequest
from api_db import (
    get_operators_with_latest,
    get_operator_history,
    get_latest_snapshots,
    get_change_events,
    get_scraper_health,
    save_push_subscription,
    delete_push_subscription,
)
```

파일 끝에 엔드포인트 3개 추가:
```python
@app.get("/push/vapid-public-key")
def get_vapid_public_key():
    return {"publicKey": os.environ.get("VAPID_PUBLIC_KEY", "")}


@app.post("/push/subscribe", status_code=201)
def subscribe(body: PushSubscriptionRequest):
    save_push_subscription(DB_PATH, body.endpoint, body.keys["p256dh"], body.keys["auth"])
    return {"ok": True}


@app.delete("/push/unsubscribe")
def unsubscribe(body: UnsubscribeRequest):
    delete_push_subscription(DB_PATH, body.endpoint)
    return {"ok": True}
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
cd /Users/jerry/dev/robotaxi-tracker/api && python -m pytest test_api.py -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 7: Commit**

```bash
git add api/models.py api/api_db.py api/main.py api/test_api.py
git commit -m "feat: add push subscription API endpoints"
```

---

## Task 5: Scraper — 변경 감지 + Push 전송

**Files:**
- Modify: `scraper/requirements.txt`
- Modify: `scraper/main.py`
- Create: `scraper/test_push.py`

- [ ] **Step 1: requirements.txt에 pywebpush 추가**

`scraper/requirements.txt`:
```
httpx==0.27.0
apscheduler==3.10.4
pywebpush==1.14.1
```

- [ ] **Step 2: 실패하는 테스트 작성**

`scraper/test_push.py` 신규 작성:
```python
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))
from db import init_db, upsert_operator, insert_snapshot, save_subscription, get_all_subscriptions
import main


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    upsert_operator(path, "AV8313426653583", "Tesla", "AV8313426653583")
    return path


def test_notify_sends_push_on_change(db_path, tmp_path):
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    insert_snapshot(db_path, "AV8313426653583", 110, "Model Y", "Authorized", "{}")
    save_subscription(db_path, "https://push.apple.com/test", "p256dh", "auth")

    fake_key = tmp_path / "private_key.pem"
    fake_key.write_text("fake")

    with patch("main.webpush") as mock_push, \
         patch("main.VAPID_PRIVATE_KEY_PATH", str(fake_key)):
        main.notify_if_changed(db_path)

    mock_push.assert_called_once()
    call_kwargs = mock_push.call_args[1]
    assert "Tesla 차량 10대 증가 (100 → 110)" in call_kwargs["data"]


def test_notify_skips_when_no_change(db_path, tmp_path):
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    save_subscription(db_path, "https://push.apple.com/test", "p256dh", "auth")

    fake_key = tmp_path / "private_key.pem"
    fake_key.write_text("fake")

    with patch("main.webpush") as mock_push, \
         patch("main.VAPID_PRIVATE_KEY_PATH", str(fake_key)):
        main.notify_if_changed(db_path)

    mock_push.assert_not_called()


def test_notify_deletes_expired_subscription(db_path, tmp_path):
    from pywebpush import WebPushException
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    insert_snapshot(db_path, "AV8313426653583", 110, "Model Y", "Authorized", "{}")
    save_subscription(db_path, "https://push.apple.com/test", "p256dh", "auth")

    fake_key = tmp_path / "private_key.pem"
    fake_key.write_text("fake")

    expired_response = MagicMock()
    expired_response.status_code = 410
    exc = WebPushException("Gone", response=expired_response)

    with patch("main.webpush", side_effect=exc), \
         patch("main.VAPID_PRIVATE_KEY_PATH", str(fake_key)):
        main.notify_if_changed(db_path)

    assert get_all_subscriptions(db_path) == []
```

- [ ] **Step 3: 테스트 실패 확인**

```bash
cd /Users/jerry/dev/robotaxi-tracker/scraper && .venv/bin/pip install pywebpush==1.14.1 -q && .venv/bin/python -m pytest test_push.py -v
```
Expected: `FAILED` (ImportError: cannot import name 'notify_if_changed' from 'main')

- [ ] **Step 4: scraper/main.py 업데이트**

`scraper/main.py` 상단 import를 아래로 교체:
```python
import json
import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from pywebpush import webpush, WebPushException
from db import init_db, upsert_operator, insert_snapshot, \
    get_all_subscriptions, delete_subscription, get_tesla_recent_snapshots
from scraper import scrape_all_operators
```

기존 상수 아래 (logging 설정 이후, `DB_PATH =` 줄 아래)에 추가:
```python
TESLA_PERMIT = "AV8313426653583"
VAPID_PRIVATE_KEY_PATH = os.environ.get("VAPID_PRIVATE_KEY_PATH", "/vapid/private_key.pem")
VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "")
```

`run_scrape()` 함수 아래에 `notify_if_changed()` 함수 추가:
```python
def notify_if_changed(db_path: str) -> None:
    if not os.path.exists(VAPID_PRIVATE_KEY_PATH):
        logger.warning("VAPID private key not found at %s, skipping push", VAPID_PRIVATE_KEY_PATH)
        return

    snapshots = get_tesla_recent_snapshots(db_path, TESLA_PERMIT, limit=2)
    if len(snapshots) < 2:
        return

    new_count = snapshots[0]["vehicle_count"]
    old_count = snapshots[1]["vehicle_count"]
    if new_count == old_count:
        return

    delta = new_count - old_count
    direction = "증가" if delta > 0 else "감소"
    body = f"Tesla 차량 {abs(delta)}대 {direction} ({old_count} → {new_count})"
    payload = json.dumps({"title": "Tesla Robotaxi 업데이트", "body": body})

    subscriptions = get_all_subscriptions(db_path)
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY_PATH,
                vapid_claims={"sub": f"mailto:{VAPID_CLAIM_EMAIL}"},
            )
            logger.info("Push sent: %s", body)
        except WebPushException as e:
            if e.response and e.response.status_code == 410:
                delete_subscription(db_path, sub["endpoint"])
                logger.info("Removed expired subscription: %s", sub["endpoint"])
            else:
                logger.error("Push failed for %s: %s", sub["endpoint"], e)
```

`run_scrape()` 함수의 `logger.info("Scrape complete: ...")` 줄 바로 뒤에 아래 줄 추가:
```python
        notify_if_changed(DB_PATH)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd /Users/jerry/dev/robotaxi-tracker/scraper && python -m pytest test_push.py -v
```
Expected: 3개 테스트 모두 PASSED

- [ ] **Step 6: 전체 scraper 테스트 확인**

```bash
cd /Users/jerry/dev/robotaxi-tracker/scraper && python -m pytest -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 7: Commit**

```bash
git add scraper/requirements.txt scraper/main.py scraper/test_push.py
git commit -m "feat: add Tesla push notification on vehicle count change"
```

---

## Task 6: Frontend — Service Worker + manifest + index.html

**Files:**
- Create: `frontend/public/sw.js`
- Create: `frontend/public/manifest.json`
- Modify: `frontend/index.html`

- [ ] **Step 1: Service Worker 작성**

`frontend/public/sw.js`:
```javascript
self.addEventListener('push', event => {
    const { title, body } = event.data.json();
    event.waitUntil(
        self.registration.showNotification(title, {
            body,
            icon: '/favicon.svg',
        })
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    event.waitUntil(clients.openWindow('/'));
});
```

- [ ] **Step 2: PWA manifest 작성**

`frontend/public/manifest.json`:
```json
{
    "name": "Texas Robotaxi Tracker",
    "short_name": "Robotaxi",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#000000",
    "theme_color": "#e82127",
    "icons": [
        {
            "src": "/favicon.svg",
            "sizes": "any",
            "type": "image/svg+xml"
        }
    ]
}
```

- [ ] **Step 3: index.html 업데이트**

`frontend/index.html`의 `<head>` 안에 아래 추가 (`<title>` 줄 바로 아래):
```html
    <link rel="manifest" href="/manifest.json" />
    <meta name="theme-color" content="#e82127" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black" />
```

- [ ] **Step 4: Commit**

```bash
git add frontend/public/sw.js frontend/public/manifest.json frontend/index.html
git commit -m "feat: add Service Worker and PWA manifest for Web Push"
```

---

## Task 7: Frontend — 알림 구독 버튼 + api.js

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/components/Header.jsx`
- Modify: `frontend/src/components/Header.module.css`

- [ ] **Step 1: api.js에 push 함수 추가**

`frontend/src/api.js` 파일 끝에 추가:
```javascript
export async function fetchVapidPublicKey() {
    const r = await fetch(`${BASE}/push/vapid-public-key`);
    if (!r.ok) throw new Error("Failed to fetch VAPID key");
    return r.json();
}

export async function subscribePush(subscription) {
    const r = await fetch(`${BASE}/push/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            endpoint: subscription.endpoint,
            keys: subscription.keys,
        }),
    });
    if (!r.ok) throw new Error("Failed to save subscription");
    return r.json();
}

export async function unsubscribePush(endpoint) {
    const r = await fetch(`${BASE}/push/unsubscribe`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint }),
    });
    if (!r.ok) throw new Error("Failed to remove subscription");
    return r.json();
}
```

- [ ] **Step 2: Header.jsx 업데이트**

`frontend/src/components/Header.jsx` 전체를 아래로 교체:
```jsx
import { useState, useEffect } from "react";
import styles from "./Header.module.css";
import { fetchVapidPublicKey, subscribePush, unsubscribePush } from "../api";

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
}

export default function Header({ lastUpdated }) {
    const ago = lastUpdated
        ? Math.round((Date.now() - new Date(lastUpdated).getTime()) / 60000)
        : null;

    const pushSupported = typeof window !== 'undefined'
        && 'serviceWorker' in navigator
        && 'PushManager' in window;

    const [subscribed, setSubscribed] = useState(false);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!pushSupported) return;
        navigator.serviceWorker.ready.then(reg =>
            reg.pushManager.getSubscription()
        ).then(sub => setSubscribed(!!sub));
    }, [pushSupported]);

    async function handleSubscribe() {
        setLoading(true);
        try {
            const reg = await navigator.serviceWorker.register('/sw.js');
            const { publicKey } = await fetchVapidPublicKey();
            const sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey),
            });
            await subscribePush(sub.toJSON());
            setSubscribed(true);
        } catch (e) {
            console.error("Subscribe failed:", e);
        } finally {
            setLoading(false);
        }
    }

    async function handleUnsubscribe() {
        setLoading(true);
        try {
            const reg = await navigator.serviceWorker.ready;
            const sub = await reg.pushManager.getSubscription();
            if (sub) {
                await unsubscribePush(sub.toJSON().endpoint);
                await sub.unsubscribe();
            }
            setSubscribed(false);
        } catch (e) {
            console.error("Unsubscribe failed:", e);
        } finally {
            setLoading(false);
        }
    }

    return (
        <header className={styles.header}>
            <div className={styles.brand}>
                <span className={styles.title}>Texas Robotaxi Tracker</span>
                <span className={styles.subtitle}>Powered by TxMCCS</span>
            </div>
            <div className={styles.right}>
                {pushSupported && (
                    <button
                        className={subscribed ? styles.notifyOff : styles.notifyOn}
                        onClick={subscribed ? handleUnsubscribe : handleSubscribe}
                        disabled={loading}
                    >
                        {loading ? "..." : subscribed ? "알림 끄기" : "알림 받기"}
                    </button>
                )}
                <div className={styles.status}>
                    <span className={styles.liveDot} />
                    <span className={styles.liveLabel}>Live</span>
                    <span className={styles.updatedAt}>
                        {ago !== null ? `Updated ${ago}m ago` : "No data"}
                    </span>
                </div>
            </div>
        </header>
    );
}
```

- [ ] **Step 3: Header.module.css 업데이트**

`frontend/src/components/Header.module.css`에서 `.status` 블록을 `.right`와 `.status`로 분리하고 버튼 스타일 추가. `.status {` 줄 바로 앞에 아래 추가:

```css
.right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.notifyOn {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  padding: 5px 12px;
  border-radius: 4px;
  border: 1px solid #e82127;
  background: transparent;
  color: #e82127;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.notifyOn:hover {
  background: #e82127;
  color: #fff;
}

.notifyOn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.notifyOff {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  padding: 5px 12px;
  border-radius: 4px;
  border: 1px solid #333;
  background: transparent;
  color: #555;
  cursor: pointer;
}

.notifyOff:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

```

그리고 기존 `.status {` 내의 `display: flex; justify-content: space-between; ...` 중 Header의 최상위 레이아웃을 `.right`가 담당하도록 아래와 같이 변경. 기존 `.header`의 `justify-content: space-between`은 유지.

- [ ] **Step 4: 빌드 및 동작 확인**

```bash
cd /Users/jerry/dev/robotaxi-tracker/frontend && npm run build
```
Expected: 빌드 성공 (warnings 허용, errors 없어야 함)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.js frontend/src/components/Header.jsx frontend/src/components/Header.module.css
git commit -m "feat: add push notification subscribe button to Header"
```

---

## Task 8: Docker 빌드 및 최종 확인

**Files:**
- 없음 (기존 파일 검증)

- [ ] **Step 1: scraper Docker 이미지 빌드 확인**

```bash
cd /Users/jerry/dev/robotaxi-tracker && docker compose build scraper
```
Expected: 빌드 성공 (pywebpush 설치 포함)

- [ ] **Step 2: api Docker 이미지 빌드 확인**

```bash
docker compose build api
```
Expected: 빌드 성공

- [ ] **Step 3: frontend Docker 이미지 빌드 확인**

```bash
docker compose build frontend
```
Expected: 빌드 성공

- [ ] **Step 4: 전체 서비스 실행**

> 사전 조건: `certs/` 디렉토리에 Tailscale cert 파일, `vapid/private_key.pem`, `.env` 파일이 있어야 함.

```bash
docker compose up -d
```

- [ ] **Step 5: API 헬스 체크**

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```
Expected: `{"status": "ok", ...}` 또는 `{"status": "no_data", ...}`

- [ ] **Step 6: VAPID 공개키 확인**

```bash
curl -s http://localhost:8000/push/vapid-public-key | python3 -m json.tool
```
Expected: `{"publicKey": "B..."}` (비어있지 않아야 함)

- [ ] **Step 7: HTTPS 프론트엔드 접속 확인**

아이폰 Safari에서 `https://YOUR_TAILSCALE_HOSTNAME:8443` 접속 → 정상 로드 확인.

- [ ] **Step 8: 홈화면에 다시 추가 + 알림 구독**

1. Safari에서 공유 버튼 → "홈 화면에 추가"
2. 앱 실행 → Header의 "알림 받기" 탭
3. 알림 권한 허용
4. `curl` 로 push 구독 확인:
```bash
curl -s http://localhost:8000/push/vapid-public-key
```

- [ ] **Step 9: 최종 commit**

```bash
git add .
git commit -m "chore: final build verification for Web Push feature"
```

---

## 사용자 체크리스트 (코드 배포 전 수동 작업)

```
[ ] tailscale cert 실행하여 certs/ 디렉토리에 .crt, .key 파일 저장
[ ] nginx.conf의 YOUR_HOSTNAME을 실제 Tailscale 호스트명으로 교체
[ ] python3 scripts/gen_vapid_keys.py 실행 후 출력값 .env에 저장
[ ] vapid/private_key.pem 파일 존재 확인
[ ] docker compose up --build 실행
[ ] 아이폰에서 HTTPS URL로 재접속 후 홈화면에 다시 추가
```
