#!/bin/bash

# 에러 발생 시 즉시 중단
set -e

echo "=========================================================="
echo "      Robotaxi Tracker Docker Service Runner              "
echo "=========================================================="

# docker compose 존재 여부 확인
if ! command -v docker &> /dev/null; then
    echo "오류: docker가 설치되어 있지 않습니다."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "오류: docker compose가 설치되어 있지 않거나 설정이 필요합니다."
    exit 1
fi

echo "[1/3] 기존에 실행 중인 Robotaxi Tracker 컨테이너 종료 중..."
docker compose down || true

echo "[2/3] Docker Compose 서비스를 빌드 및 백그라운드 구동 중..."
docker compose up --build -d

echo "[3/3] 실행 중인 Docker 컨테이너 상태 확인:"
echo "----------------------------------------------------------"
docker compose ps
echo "----------------------------------------------------------"

echo ""
echo "서비스가 성공적으로 시작되었습니다!"
echo "- 프론트엔드 대시보드: https://localhost:8443"
echo "- 백엔드 API 서버    : http://localhost:8000"
echo ""
echo "스크래퍼 상태: curl -s http://localhost:8000/health"
echo "실시간 로그:   docker compose logs -f"
echo "=========================================================="
