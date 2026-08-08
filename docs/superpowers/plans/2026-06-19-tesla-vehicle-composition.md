# Tesla Vehicle Composition Breakdown Implementation Plan

> **Historical plan (2026-06-19).** Vehicle list API is now company-based — see [DATA_SOURCE](../../DATA_SOURCE.md) and [composition design](../specs/2026-06-19-tesla-vehicle-composition-design.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tesla SummaryCard에 차량 모델×연도별 구성 breakdown을 표시한다 (예: Model Y 2026 × 48대).

**Architecture:** `snapshots.vehicle_composition` JSON 컬럼을 추가해 스크레이퍼가 make/model/year 집계를 저장하고, API가 파싱해서 노출하며, 프론트엔드의 Tesla 카드에서 렌더링한다.

**Tech Stack:** Python/FastAPI (API), SQLite (DB), React/Vite (frontend), pytest (testing)

## Global Constraints

- Python 파일은 scraper/ 내에서 `python -m pytest` 또는 `pytest` 실행
- API 테스트: `cd api && python -m pytest test_api.py -v`
- Scraper 테스트: `cd scraper && python -m pytest test_scraper.py -v`
- DB 마이그레이션: `scraper/db.py`의 `init_db()`에서 처리 (scraper가 DB 소유자)
- 프론트엔드 빌드: `cd frontend && npm run build`
- 기존 `vehicle_type` 필드는 변경하지 않는다 (backward compat)

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `scraper/scraper.py` | Modify | `parse_vehicles_response()` — composition 집계 추가 |
| `scraper/db.py` | Modify | `init_db()` migration + `insert_snapshot()` 파라미터 추가 |
| `scraper/main.py` | Modify | `insert_snapshot()` 호출에 `vehicle_composition` 전달 |
| `scraper/test_scraper.py` | Modify | `parse_vehicles_response` 신규 필드 테스트 추가 |
| `scraper/test_db.py` | Modify | migration + insert/select round-trip 테스트 추가 |
| `api/models.py` | Modify | `OperatorSummary`, `LatestSnapshot`, `SnapshotPoint`에 필드 추가 |
| `api/api_db.py` | Modify | SELECT에 `vehicle_composition` 포함, JSON 파싱 |
| `api/test_api.py` | Modify | API 응답에 `vehicle_composition` 포함 검증 |
| `frontend/src/components/SummaryCards.jsx` | Modify | Breakdown 리스트 렌더링 |
| `frontend/src/components/SummaryCards.module.css` | Modify | Breakdown 스타일 추가 |

---

### Task 1: Scraper — `parse_vehicles_response()` composition 집계

**Files:**
- Modify: `scraper/scraper.py:44-59`
- Modify: `scraper/test_scraper.py`

**Interfaces:**
- Produces: `parse_vehicles_response(api_response)` returns dict with new key:
  ```python
  {
    "vehicle_count": int,
    "vehicle_type": str,
    "vehicle_composition": list[dict],  # new
  }
  # vehicle_composition item: {"make": str, "model": str, "year": int|None, "count": int}
  # sorted by count descending
  ```

- [ ] **Step 1: Write failing tests in `scraper/test_scraper.py`**

기존 테스트 파일 끝에 다음을 추가한다:

```python
def test_parse_vehicles_response_composition_single_group():
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN2", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN3", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
        ]
    }
    result = parse_vehicles_response(api_response)
    assert result["vehicle_composition"] == [
        {"make": "TESLA", "model": "Model Y", "year": 2026, "count": 3}
    ]


def test_parse_vehicles_response_composition_multiple_groups_sorted():
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA", "model": "Cybercab", "modelYear": 2026},
            {"vin": "VIN2", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN3", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN4", "make": "TESLA", "model": "Model Y", "modelYear": 2025},
        ]
    }
    result = parse_vehicles_response(api_response)
    # sorted by count desc
    assert result["vehicle_composition"][0] == {"make": "TESLA", "model": "Model Y", "year": 2026, "count": 2}
    assert len(result["vehicle_composition"]) == 3


def test_parse_vehicles_response_composition_empty():
    api_response = {"vehicles": []}
    result = parse_vehicles_response(api_response)
    assert result["vehicle_composition"] == []


def test_parse_vehicles_response_composition_null_year():
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA", "model": "Model Y"},  # no modelYear
        ]
    }
    result = parse_vehicles_response(api_response)
    assert result["vehicle_composition"] == [
        {"make": "TESLA", "model": "Model Y", "year": None, "count": 1}
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scraper && python -m pytest test_scraper.py -v -k "composition"
```

Expected: 4 tests FAIL with `KeyError: 'vehicle_composition'`

- [ ] **Step 3: Implement in `scraper/scraper.py`**

`parse_vehicles_response()` 함수 전체를 아래로 교체:

```python
def parse_vehicles_response(api_response: dict) -> dict:
    """Extract vehicle count, dominant model, and composition breakdown."""
    vehicles = api_response.get("vehicles", [])
    count = len(vehicles)
    if count == 0:
        return {"vehicle_count": 0, "vehicle_type": "", "vehicle_composition": []}

    model_counts: dict[str, int] = {}
    composition_counts: dict[tuple, int] = {}
    for v in vehicles:
        model = v.get("model", "").strip()
        if model:
            model_counts[model] = model_counts.get(model, 0) + 1
        key = (v.get("make", "").strip(), model, v.get("modelYear"))
        composition_counts[key] = composition_counts.get(key, 0) + 1

    dominant_model = max(model_counts, key=lambda m: model_counts[m]) if model_counts else ""

    composition = sorted(
        [
            {"make": make, "model": model, "year": year, "count": cnt}
            for (make, model, year), cnt in composition_counts.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    return {
        "vehicle_count": count,
        "vehicle_type": dominant_model,
        "vehicle_composition": composition,
    }
```

- [ ] **Step 4: Run all scraper tests**

```bash
cd scraper && python -m pytest test_scraper.py -v
```

Expected: 전체 PASS (기존 5개 + 신규 4개 = 9개)

- [ ] **Step 5: Commit**

```bash
git add scraper/scraper.py scraper/test_scraper.py
git commit -m "feat: add vehicle_composition to parse_vehicles_response"
```

---

### Task 2: Scraper DB — migration + insert_snapshot 업데이트

**Files:**
- Modify: `scraper/db.py:6-41` (init_db), `scraper/db.py:62-80` (insert_snapshot)
- Modify: `scraper/test_db.py`

**Interfaces:**
- Consumes: `vehicle_composition` as JSON string (caller passes `json.dumps(composition_list)`)
- Produces: `insert_snapshot(db_path, operator_id, vehicle_count, vehicle_type, status, raw_json, vehicle_composition)` — `vehicle_composition` 파라미터 추가 (기본값 `""`)

- [ ] **Step 1: Write failing tests in `scraper/test_db.py`**

기존 파일 내용을 읽은 후, 끝에 다음을 추가:

```python
def test_init_db_creates_vehicle_composition_column(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(snapshots)").fetchall()]
    conn.close()
    assert "vehicle_composition" in cols


def test_insert_snapshot_stores_composition(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_operator(db_path, "AV001", "Tesla", "AV001")
    composition = json.dumps([{"make": "TESLA", "model": "Model Y", "year": 2026, "count": 5}])
    insert_snapshot(db_path, "AV001", 5, "Model Y", "authorized", "{}", composition)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT vehicle_composition FROM snapshots WHERE operator_id='AV001'").fetchone()
    conn.close()
    assert json.loads(row["vehicle_composition"]) == [
        {"make": "TESLA", "model": "Model Y", "year": 2026, "count": 5}
    ]


def test_insert_snapshot_without_composition_defaults_to_empty(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_operator(db_path, "AV001", "Tesla", "AV001")
    insert_snapshot(db_path, "AV001", 5, "Model Y", "authorized", "{}")

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT vehicle_composition FROM snapshots WHERE operator_id='AV001'").fetchone()
    conn.close()
    assert row[0] is None or row[0] == ""
```

파일 상단에 `import json` 추가 필요.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scraper && python -m pytest test_db.py -v -k "composition"
```

Expected: 3 tests FAIL

- [ ] **Step 3: Update `scraper/db.py` — init_db migration**

`init_db()` 함수 내 `executescript` 블록 끝, `conn.commit()` 전에 다음을 추가:

```python
        # Migration: add vehicle_composition column if not present
        try:
            conn.execute("ALTER TABLE snapshots ADD COLUMN vehicle_composition TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
```

- [ ] **Step 4: Update `scraper/db.py` — insert_snapshot 파라미터 추가**

`insert_snapshot()` 함수 시그니처와 본문을 아래로 교체:

```python
def insert_snapshot(
    db_path: str,
    operator_id: str,
    vehicle_count: int,
    vehicle_type: str,
    status: str,
    raw_json: str,
    vehicle_composition: str = "",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("""
            INSERT INTO snapshots (operator_id, vehicle_count, vehicle_type, status, raw_json, vehicle_composition, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (operator_id, vehicle_count, vehicle_type, status, raw_json, vehicle_composition or None, now))
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run all DB tests**

```bash
cd scraper && python -m pytest test_db.py -v
```

Expected: 전체 PASS

- [ ] **Step 6: Commit**

```bash
git add scraper/db.py scraper/test_db.py
git commit -m "feat: add vehicle_composition column to snapshots"
```

---

### Task 3: Scraper main — insert_snapshot 호출에 composition 전달

**Files:**
- Modify: `scraper/main.py`

**Interfaces:**
- Consumes: `parse_vehicles_response()` → `vehicle_composition: list[dict]`
- Consumes: `insert_snapshot()` → `vehicle_composition: str` (JSON string)

- [ ] **Step 1: Read `scraper/main.py`**

파일을 읽어 `insert_snapshot` 호출 위치를 확인한다.

- [ ] **Step 2: Update the call site**

`scraper/main.py`에서 `insert_snapshot(...)` 호출을 찾아 `vehicle_composition` 인자를 추가한다.

기존 호출 예시:
```python
insert_snapshot(
    db_path,
    result["operator_id"],
    result["vehicle_count"],
    result["vehicle_type"],
    result["status"],
    result["raw_json"],
)
```

변경 후:
```python
import json as _json  # 파일 상단에 없으면 추가

insert_snapshot(
    db_path,
    result["operator_id"],
    result["vehicle_count"],
    result["vehicle_type"],
    result["status"],
    result["raw_json"],
    _json.dumps(result.get("vehicle_composition", [])),
)
```

파일 상단에 `import json` 이 없으면 추가. 변수명 충돌 시 `import json` 그대로 사용.

- [ ] **Step 3: Verify scraper main still imports cleanly**

```bash
cd scraper && python -c "import main; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add scraper/main.py
git commit -m "feat: pass vehicle_composition through scraper pipeline"
```

---

### Task 4: API — models + api_db 업데이트

**Files:**
- Modify: `api/models.py`
- Modify: `api/api_db.py`
- Modify: `api/test_api.py`

**Interfaces:**
- Produces: `GET /operators` 응답의 각 항목에 `vehicle_composition: list[dict] | null`
- Produces: `GET /snapshots/latest` 응답의 각 항목에 `vehicle_composition: list[dict] | null`

- [ ] **Step 1: Write failing test in `api/test_api.py`**

기존 `test_get_operators` 옆에 다음 테스트 추가:

```python
def test_get_operators_includes_composition(client):
    r = client.get("/operators")
    assert r.status_code == 200
    data = r.json()
    # vehicle_composition이 존재해야 함 (None이어도 키는 있어야 함)
    assert "vehicle_composition" in data[0]


def test_get_snapshots_latest_includes_composition(client):
    r = client.get("/snapshots/latest")
    assert r.status_code == 200
    data = r.json()
    assert "vehicle_composition" in data[0]
```

> Note: `client` fixture는 `insert_snapshot(db, "AV001", 42, "Model Y", "Authorized", "{}")` — composition 없이 호출하므로 결과는 `None`. 키 존재 여부만 검증.

- [ ] **Step 2: Run to verify they fail**

```bash
cd api && python -m pytest test_api.py -v -k "composition"
```

Expected: FAIL — `vehicle_composition` key missing

- [ ] **Step 3: Update `api/models.py`**

`OperatorSummary`, `LatestSnapshot`, `SnapshotPoint` 각각에 필드 추가:

```python
from typing import Optional, Any

class OperatorSummary(BaseModel):
    id: str
    name: str
    permit_number: Optional[str] = None
    first_seen_at: Optional[str] = None
    vehicle_count: Optional[int] = None
    vehicle_type: Optional[str] = None
    vehicle_composition: Optional[list[Any]] = None  # new
    status: Optional[str] = None
    captured_at: Optional[str] = None


class SnapshotPoint(BaseModel):
    vehicle_count: int
    vehicle_type: Optional[str] = None
    vehicle_composition: Optional[list[Any]] = None  # new
    status: Optional[str] = None
    captured_at: str


class LatestSnapshot(BaseModel):
    operator_id: str
    name: str
    vehicle_count: int
    vehicle_type: Optional[str] = None
    vehicle_composition: Optional[list[Any]] = None  # new
    status: Optional[str] = None
    captured_at: str
```

- [ ] **Step 4: Update `api/api_db.py` — SELECT에 vehicle_composition 추가**

`get_latest_snapshots()` 쿼리에 `s.vehicle_composition` 추가:

```python
def get_latest_snapshots(db_path: str) -> list[dict]:
    conn = _conn(db_path)
    try:
        rows = conn.execute("""
            SELECT s.operator_id, o.name, s.vehicle_count, s.vehicle_type,
                   s.vehicle_composition, s.status, s.captured_at
            FROM snapshots s
            JOIN operators o ON o.id = s.operator_id
            WHERE s.id = (
                SELECT id FROM snapshots s2
                WHERE s2.operator_id = s.operator_id
                ORDER BY captured_at DESC LIMIT 1
            )
            ORDER BY s.vehicle_count DESC
        """).fetchall()
    finally:
        conn.close()
    return [_parse_composition(dict(r)) for r in rows]
```

`get_operators_with_latest()` 쿼리에도 `s.vehicle_composition` 추가:

```python
def get_operators_with_latest(db_path: str) -> list[dict]:
    conn = _conn(db_path)
    try:
        rows = conn.execute("""
            SELECT o.id, o.name, o.permit_number, o.first_seen_at,
                   s.vehicle_count, s.vehicle_type, s.vehicle_composition, s.status, s.captured_at
            FROM operators o
            LEFT JOIN snapshots s ON s.id = (
                SELECT id FROM snapshots s2
                WHERE s2.operator_id = o.id
                ORDER BY captured_at DESC LIMIT 1
            )
            ORDER BY s.vehicle_count DESC NULLS LAST
        """).fetchall()
    finally:
        conn.close()
    return [_parse_composition(dict(r)) for r in rows]
```

파일 상단에 `import json` 추가 후, 헬퍼 함수 추가:

```python
import json

def _parse_composition(row: dict) -> dict:
    """JSON string → list for vehicle_composition field."""
    raw = row.get("vehicle_composition")
    if raw:
        try:
            row["vehicle_composition"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            row["vehicle_composition"] = None
    else:
        row["vehicle_composition"] = None
    return row
```

- [ ] **Step 5: Run all API tests**

```bash
cd api && python -m pytest test_api.py -v
```

Expected: 전체 PASS

- [ ] **Step 6: Commit**

```bash
git add api/models.py api/api_db.py api/test_api.py
git commit -m "feat: expose vehicle_composition in API responses"
```

---

### Task 5: Frontend — Tesla 카드에 Breakdown 표시

**Files:**
- Modify: `frontend/src/components/SummaryCards.jsx`
- Modify: `frontend/src/components/SummaryCards.module.css`

**Interfaces:**
- Consumes: `tesla.vehicle_composition: Array<{make, model, year, count}> | null`

- [ ] **Step 1: CSS 추가 — `SummaryCards.module.css` 끝에 추가**

```css
/* ── Vehicle composition breakdown (Tesla card) ── */
.compositionList {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #1a1a1a;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.compositionRow {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.compositionModel {
  font-size: 11px;
  font-weight: 600;
  color: #666;
  letter-spacing: 0.04em;
  min-width: 80px;
}

.compositionYear {
  font-size: 11px;
  color: #333;
  letter-spacing: 0.04em;
  min-width: 36px;
}

.compositionCount {
  font-size: 13px;
  font-weight: 700;
  color: #999;
  margin-left: auto;
  letter-spacing: -0.01em;
}
```

- [ ] **Step 2: JSX 업데이트 — `SummaryCards.jsx`**

Tesla 카드 내 `.teslaLeft` div를 아래로 교체 (`teslaCard` div 구조 전체 유지):

```jsx
<div className={styles.teslaLeft}>
  <div className={styles.teslaName}>Tesla Robotaxi</div>
  <div className={styles.teslaCount}>{tesla.vehicle_count ?? "—"}</div>
  <div className={styles.teslaLabel}>Vehicles Permitted · Texas</div>
  {tesla.vehicle_composition && tesla.vehicle_composition.length > 0 && (
    <div className={styles.compositionList}>
      {tesla.vehicle_composition.map((item, i) => (
        <div key={i} className={styles.compositionRow}>
          <span className={styles.compositionModel}>{item.model}</span>
          <span className={styles.compositionYear}>{item.year ?? "—"}</span>
          <span className={styles.compositionCount}>{item.count}대</span>
        </div>
      ))}
    </div>
  )}
</div>
```

- [ ] **Step 3: 프론트엔드 빌드 확인**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: `built in Xs` — 에러 없음

- [ ] **Step 4: 시각적 확인**

개발 서버를 실행해 Tesla 카드에 breakdown이 표시되는지 확인:

```bash
cd frontend && npm run dev
```

브라우저에서 확인:
- Tesla 카드 하단에 구분선 후 모델/연도/대수 행이 표시됨
- `vehicle_composition`이 null인 경우 (기존 스냅샷) breakdown 영역이 표시되지 않음

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SummaryCards.jsx frontend/src/components/SummaryCards.module.css
git commit -m "feat: show vehicle composition breakdown in Tesla summary card"
```

---

## Self-Review

**Spec coverage:**
- ✅ `snapshots.vehicle_composition` 컬럼 추가 (Task 2)
- ✅ `parse_vehicles_response()` composition 집계 (Task 1)
- ✅ `insert_snapshot()` 파라미터 추가 (Task 2)
- ✅ `scraper/main.py` 호출 업데이트 (Task 3)
- ✅ API 모델 필드 추가 (Task 4)
- ✅ `api_db.py` SELECT + JSON 파싱 (Task 4)
- ✅ Tesla 카드 breakdown 렌더링 (Task 5)
- ✅ Tesla 전용 (다른 오퍼레이터 변경 없음) (Task 5 — `vehicle_composition` null-safe 조건부 렌더링)
- ✅ 기존 스냅샷 null 처리 (Task 4 `_parse_composition`, Task 5 조건부 렌더링)

**Placeholder scan:** 없음 — 모든 스텝에 실제 코드 포함

**Type consistency:**
- `vehicle_composition` DB: TEXT (JSON string)
- `vehicle_composition` Python dict return: `list[dict]` with keys `make, model, year, count`
- `vehicle_composition` API model: `Optional[list[Any]]`
- `vehicle_composition` JS/JSX: `Array<{make, model, year, count}>`
- 일관성 확인 ✅
