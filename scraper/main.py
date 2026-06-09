import json
import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from pywebpush import webpush, WebPushException
from db import init_db, upsert_operator, insert_snapshot, \
    get_all_subscriptions, delete_subscription, get_tesla_recent_snapshots
from scraper import scrape_all_operators

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/data/robotaxi.db")
TESLA_PERMIT = "AV8313426653583"
VAPID_PRIVATE_KEY_PATH = os.environ.get("VAPID_PRIVATE_KEY_PATH", "/vapid/private_key.pem")
VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "")


def run_scrape():
    logger.info("Starting scrape run")
    try:
        results = scrape_all_operators()
        for r in results:
            upsert_operator(DB_PATH, r["operator_id"], r["name"], r["permit_number"])
            insert_snapshot(
                DB_PATH,
                r["operator_id"],
                r["vehicle_count"],
                r["vehicle_type"],
                r["status"],
                r["raw_json"],
            )
        logger.info("Scrape complete: %d operators saved", len(results))
        notify_if_changed(DB_PATH)
    except Exception as e:
        logger.error("Scrape run failed: %s", e, exc_info=True)


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
    payload = json.dumps({"title": "Tesla Robotaxi 업데이트", "body": body}, ensure_ascii=False)

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
            if e.response and e.response.status_code in (404, 410):
                delete_subscription(db_path, sub["endpoint"])
                logger.info("Removed expired subscription: %s", sub["endpoint"])
            else:
                logger.error("Push failed for %s: %s", sub["endpoint"], e)


if __name__ == "__main__":
    init_db(DB_PATH)
    logger.info("DB initialized at %s", DB_PATH)

    # Run once immediately on startup
    run_scrape()

    scheduler = BlockingScheduler()
    scheduler.add_job(run_scrape, "interval", minutes=15)
    logger.info("Scheduler started: every 15 minutes")
    scheduler.start()
