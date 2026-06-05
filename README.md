# Texas Robotaxi Tracker

Texas 주 교통부(TxMCCS)에 등록된 자율주행차 운영사의 허가 차량 수를 실시간으로 추적하는 대시보드입니다. Tesla Robotaxi를 중심으로 Waymo, Aurora 등 경쟁사 현황을 함께 모니터링합니다.

![dashboard](docs/screenshot.png)

## 구성

```
├── scraper/     # TxMCCS API 폴링 (15분 간격)
├── api/         # FastAPI REST API
├── frontend/    # React + Recharts 대시보드
└── docker-compose.yml
```

| 서비스 | 포트 | 설명 |
|--------|------|------|
| frontend | 8080 | 대시보드 UI |
| api | 8000 | REST API |
| scraper | — | 백그라운드 수집기 |

## 실행

```bash
./run_docker.sh
```

- 프론트엔드: http://localhost:8080
- API: http://localhost:8000

도커가 실행 중이면 스크래퍼가 시작 시 즉시 한 번, 이후 **15분마다** TxMCCS에서 데이터를 수집합니다.

## API

```
GET /snapshots/latest        # 운영사별 최신 차량 수
GET /operators               # 전체 운영사 목록
GET /operators/{id}/history  # 특정 운영사 시계열 (days=7|30|전체)
GET /events/changes          # 차량 수 변경 이벤트 로그
GET /health                  # 마지막 스크래핑 시각
```

## 데이터 출처

[Texas Motor Carrier Credentialing System (TxMCCS)](https://www.txmccs.com/) — 공개 API, 인증 불필요
