import os
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
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

DB_PATH = os.environ.get("DB_PATH", "/data/robotaxi.db")

app = FastAPI(title="Robotaxi Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/operators", response_model=list[OperatorSummary])
def list_operators():
    return get_operators_with_latest(DB_PATH)


@app.get("/operators/{operator_id}/history", response_model=list[SnapshotPoint])
def operator_history(
    operator_id: str,
    days: Optional[int] = Query(None, description="7, 30, or omit for all"),
):
    return get_operator_history(DB_PATH, operator_id, days)


@app.get("/snapshots/latest", response_model=list[LatestSnapshot])
def latest_snapshots():
    return get_latest_snapshots(DB_PATH)


@app.get("/events/changes", response_model=list[ChangeEvent])
def change_events(page: int = Query(1, ge=1)):
    return get_change_events(DB_PATH, page=page)


@app.get("/health", response_model=HealthResponse)
def health():
    data = get_scraper_health(DB_PATH)
    status = "ok" if data["last_scrape_at"] else "no_data"
    return {**data, "status": status}


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
