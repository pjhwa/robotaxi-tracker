import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from db import init_db, upsert_operator, insert_snapshot
from scraper import scrape_all_operators

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/data/robotaxi.db")


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
    except Exception as e:
        logger.error("Scrape run failed: %s", e)


if __name__ == "__main__":
    init_db(DB_PATH)
    logger.info("DB initialized at %s", DB_PATH)

    # Run once immediately on startup
    run_scrape()

    scheduler = BlockingScheduler()
    scheduler.add_job(run_scrape, "interval", minutes=15)
    logger.info("Scheduler started: every 15 minutes")
    scheduler.start()
