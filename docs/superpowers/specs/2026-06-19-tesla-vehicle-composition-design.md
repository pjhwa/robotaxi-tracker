# Tesla Vehicle Composition Breakdown — Design Spec

**Date:** 2026-06-19  
**Status:** Implemented  

> **Note (2026-08-08):** Vehicle list source is now  
> `GET /api/TruckStop/companies/{businessEntityId}/automated-motor-vehicles`  
> (not the removed `/operators/{id}/vehicles`). Composition parsing is unchanged.
## Goal

Display Tesla Robotaxi의 차량 구성(생산연도 × 모델별 대수)을 Tesla SummaryCard에 표시한다.  
주목적: Model Y 외에 Cybercab이 허가 목록에 추가되는 시점을 대시보드에서 바로 확인하기 위함.  
다른 오퍼레이터 카드는 변경하지 않는다.

---

## Data Model

### `snapshots` 테이블에 컬럼 추가

```sql
ALTER TABLE snapshots ADD COLUMN vehicle_composition TEXT;
```

값 형식 (JSON array, 내림차순 정렬):
```json
[
  {"make": "TESLA", "model": "Model Y", "year": 2026, "count": 48},
  {"make": "TESLA", "model": "Model Y", "year": 2025, "count": 3}
]
```

- 기존 스냅샷은 `vehicle_composition = NULL` (마이그레이션 불필요)
- 컬럼 없는 구버전 DB에 대해 `ALTER TABLE ADD COLUMN`은 멱등적으로 적용 (`IF NOT EXISTS` 불가시 try/except)

---

## Scraper Changes (`scraper/`)

### `scraper.py` — `parse_vehicles_response()`

기존 dominant model 집계에 더해 make/model/year 조합별 count를 집계한다.

반환값 추가:
```python
{
  "vehicle_count": 51,
  "vehicle_type": "Model Y",           # 기존 유지
  "vehicle_composition": [             # 신규
    {"make": "TESLA", "model": "Model Y", "year": 2026, "count": 48},
    {"make": "TESLA", "model": "Model Y", "year": 2025, "count": 3}
  ]
}
```

집계 키: `(make, model, modelYear)` — 내림차순 count 정렬.  
`modelYear`가 None인 항목은 `year: null`로 저장.

### `scraper/db.py` — `insert_snapshot()`

- `vehicle_composition` 파라미터 추가 (JSON string)
- INSERT 쿼리에 컬럼 추가

---

## API Changes (`api/`)

### `api/api_db.py` — `get_latest_snapshots()`, `get_operators_with_latest()`

- SELECT에 `s.vehicle_composition` 추가

### `api/models.py`

`OperatorSummary`, `LatestSnapshot`, `SnapshotPoint`에 필드 추가:
```python
vehicle_composition: Optional[list[dict]] = None
```

API 응답에서 `vehicle_composition`은 JSON string → list 파싱 필요 (`json.loads`).

---

## Frontend Changes (`frontend/`)

### `SummaryCards.jsx`

Tesla 카드(`teslaCard`)에 `vehicle_composition` breakdown 표시:
- `tesla.vehicle_composition`이 있을 때만 렌더링
- 항목당: `{model} {year}` + count (우측 정렬)
- make는 Tesla만이므로 생략 (Tesla 전용 기능이기 때문)
- Cybercab 추가 시 자동으로 새 행으로 표시됨

레이아웃:
```
[Tesla 카드 기존 영역]
──────────────────────
Model Y   2026    48대
Model Y   2025     3대
```

### `api.js`

`vehicle_composition` 파싱은 백엔드에서 처리하므로 프론트 변경 최소.

---

## Migration Strategy

1. `scraper/db.py`의 `init_db()`에서 `ALTER TABLE snapshots ADD COLUMN vehicle_composition TEXT` 실행 (try/except로 이미 존재하는 경우 무시)
2. 다음 스크레이핑 실행 시 새 스냅샷부터 `vehicle_composition` 자동 저장
3. 기존 스냅샷은 NULL — 프론트에서 null-safe 처리

---

## Out of Scope

- 다른 오퍼레이터의 vehicle_composition 표시
- 히스토리 뷰(TrendChart)에서의 모델별 분리
- VIN 수준 데이터 저장
