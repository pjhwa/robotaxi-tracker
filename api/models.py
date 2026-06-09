from pydantic import BaseModel
from typing import Optional


class OperatorSummary(BaseModel):
    id: str
    name: str
    permit_number: Optional[str] = None
    first_seen_at: Optional[str] = None
    vehicle_count: Optional[int] = None
    vehicle_type: Optional[str] = None
    status: Optional[str] = None
    captured_at: Optional[str] = None


class SnapshotPoint(BaseModel):
    vehicle_count: int
    vehicle_type: Optional[str] = None
    status: Optional[str] = None
    captured_at: str


class ChangeEvent(BaseModel):
    operator_id: str
    operator_name: str
    old_count: int
    new_count: int
    delta: int
    captured_at: str


class LatestSnapshot(BaseModel):
    operator_id: str
    name: str
    vehicle_count: int
    vehicle_type: Optional[str] = None
    status: Optional[str] = None
    captured_at: str


class HealthResponse(BaseModel):
    last_scrape_at: Optional[str] = None
    status: str


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: PushKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str
