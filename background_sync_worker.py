"""
Background worker for automatic Shopify syncing.
Run this as a separate process in production for real-time data updates.

Usage:
    python background_sync_worker.py

For systemd service, see README.md for deployment instructions.
"""

import logging
import sys
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from utils.db import init_db, get_setting, set_setting
from utils.shopify_realtime_sync import RealtimeSyncEngine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("sync_worker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SyncWorker:
    def __init__(self):
        init_db()
        self.engine = RealtimeSyncEngine()
        self.scheduler = BackgroundScheduler()

    def sync_task(self):
        """Run all configured sync tasks"""
        if not get_setting("shopify_access_token"):
            logger.warning("Shopify not connected, skipping sync")
            return

        try:
            config = self.engine.get_auto_sync_config()

            if config.get("sync_products"):
                logger.info("Starting products sync...")
                result = self.engine.sync_products(limit=100)
                logger.info(f"Products sync: {result['status']} - {result.get('imported', 0)} imported, {result.get('updated', 0)} updated")

            if config.get("sync_orders"):
                logger.info("Starting orders sync...")
                result = self.engine.sync_orders(limit=100, since_last_sync=True)
                logger.info(f"Orders sync: {result['status']} - {result.get('imported', 0)} imported, {result.get('updated', 0)} updated")

            if config.get("sync_customers"):
                logger.info("Starting customers sync...")
                result = self.engine.sync_customers(limit=100)
                logger.info(f"Customers sync: {result['status']} - {result.get('imported', 0)} imported, {result.get('updated', 0)} updated")

            set_setting("last_auto_sync_timestamp", datetime.now().isoformat())
            logger.info("Auto sync completed successfully")

        except Exception as e:
            logger.error(f"Auto sync failed: {e}", exc_info=True)

    def start(self):
        """Start the background scheduler"""
        if get_setting("auto_sync_enabled") != "true":
            logger.warning("Auto sync is disabled in settings")
            return False

        try:
            interval = int(get_setting("auto_sync_interval_minutes", "15"))
            logger.info(f"Starting sync worker with {interval} minute interval")

            self.scheduler.add_job(
                self.sync_task,
                "interval",
                minutes=interval,
                id="shopify_sync",
                name="Shopify Auto Sync",
                replace_existing=True
            )

            # Run once immediately
            logger.info("Running initial sync...")
            self.sync_task()

            self.scheduler.start()
            logger.info("Sync worker started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start sync worker: {e}", exc_info=True)
            return False

    def stop(self):
        """Stop the background scheduler gracefully"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("Sync worker stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")


def main():
    worker = SyncWorker()

    if not worker.start():
        logger.error("Failed to start worker")
        sys.exit(1)

    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        worker.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
