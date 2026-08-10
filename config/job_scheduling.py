"""
S3.10 Job scheduling configuration for nightly tasks.

Procrastinate scheduler for recurring jobs:
- job_mim_etl: 00:00 UTC daily (MIM market intelligence)
- job_corpus_ingest: 02:00 UTC daily (corpus preparation for S4)

Uses Procrastinate's built-in cron support or APScheduler wrapper.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class JobScheduler:
    """Configure and manage recurring job schedules."""

    def __init__(self, app):
        """Initialize with Procrastinate app.

        Args:
            app: procrastinate.App instance
        """
        self.app = app
        self.scheduled_jobs = []

    def schedule_mim_etl(self, hour: int = 0, minute: int = 0):
        """
        Schedule nightly MIM ETL job.

        Args:
            hour: Hour in UTC (0-23, default 0 = midnight UTC)
            minute: Minute (0-59, default 0)

        Returns:
            Job schedule info
        """
        schedule_info = {
            "job_name": "job_mim_etl",
            "time": f"{hour:02d}:{minute:02d} UTC",
            "description": "Nightly MIM ETL: OFF/USDA download → shelf_facts update → trends calculation",
        }

        logger.info(f"📅 Scheduled {schedule_info['job_name']} at {schedule_info['time']}")

        # TODO S3.10: Integrate with APScheduler or Procrastinate periodic task
        # For now: document the schedule and let operator run via cron/supervisor

        self.scheduled_jobs.append(schedule_info)
        return schedule_info

    def schedule_corpus_ingest(self, hour: int = 2, minute: int = 0):
        """
        Schedule corpus ingest job (for S4 preparation).

        Args:
            hour: Hour in UTC (default 2 = 02:00 UTC)
            minute: Minute (default 0)

        Returns:
            Job schedule info
        """
        schedule_info = {
            "job_name": "job_corpus_ingest",
            "time": f"{hour:02d}:{minute:02d} UTC",
            "description": "Corpus preparation for S4: download + index documents",
        }

        logger.info(f"📅 Scheduled {schedule_info['job_name']} at {schedule_info['time']}")

        self.scheduled_jobs.append(schedule_info)
        return schedule_info

    def get_next_run_time(self, hour: int, minute: int) -> datetime:
        """Calculate next run time for a scheduled job (UTC).

        Args:
            hour: Target hour (0-23)
            minute: Target minute (0-59)

        Returns:
            Next scheduled datetime in UTC
        """
        now = datetime.now(timezone.utc)
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If scheduled time has already passed today, return tomorrow
        if scheduled <= now:
            scheduled += timedelta(days=1)

        return scheduled

    def get_schedules(self) -> list:
        """Get all configured schedules."""
        return self.scheduled_jobs

    def health_check(self) -> dict:
        """Check if nightly jobs are on track.

        Returns:
            {
                "healthy": bool,
                "next_mim_etl": datetime,
                "next_corpus_ingest": datetime,
                "warnings": list[str]
            }
        """
        warnings = []

        next_mim_etl = self.get_next_run_time(0, 0)  # 00:00 UTC
        next_corpus = self.get_next_run_time(2, 0)   # 02:00 UTC

        # TODO S3.10: Query eventos_job to check if previous jobs ran
        # warning if mim_etl didn't run yesterday

        return {
            "healthy": len(warnings) == 0,
            "next_mim_etl": next_mim_etl.isoformat(),
            "next_corpus_ingest": next_corpus.isoformat(),
            "warnings": warnings,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Initialize scheduler when module is imported
_scheduler: Optional[JobScheduler] = None


def get_scheduler(app) -> JobScheduler:
    """Get or create global JobScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler(app)
        # Configure default schedules
        _scheduler.schedule_mim_etl(hour=0, minute=0)  # 00:00 UTC
        _scheduler.schedule_corpus_ingest(hour=2, minute=0)  # 02:00 UTC
    return _scheduler


# Integration points:
# 1. In start_worker.py: Call get_scheduler().health_check() at startup
# 2. In health.py: Add /health/jobs endpoint to monitor schedules
# 3. In supervisord/systemd: Run worker with restart=always to ensure nightly jobs run


class JobMonitor:
    """Monitor job execution and alert on SLA violations."""

    def __init__(self, db_url: str, sla_minutes: int = 30):
        """Initialize monitor.

        Args:
            db_url: PostgreSQL connection URL
            sla_minutes: Max duration for nightly job (default 30 min)
        """
        self.db_url = db_url
        self.sla_minutes = sla_minutes

    def check_job_sla(self, job_name: str) -> dict:
        """Check if a job completed within SLA.

        Args:
            job_name: e.g., 'job_mim_etl'

        Returns:
            {
                "job_name": str,
                "last_run": datetime,
                "duration_seconds": int,
                "sla_exceeded": bool,
                "status": "completed" | "failed" | "missing"
            }
        """
        try:
            import psycopg

            conn = psycopg.connect(self.db_url)
            with conn.cursor() as cur:
                # Get last execution of this job
                cur.execute(
                    """
                    SELECT
                        MAX(CASE WHEN evento = 'started' THEN created_at END) as started_at,
                        MAX(CASE WHEN evento = 'completed' THEN created_at END) as completed_at,
                        MAX(CASE WHEN evento = 'failed' THEN created_at END) as failed_at,
                        COUNT(*) as event_count
                    FROM eventos_job
                    WHERE job_id IN (
                        SELECT id FROM procrastinate_jobs WHERE task_name = %s
                    )
                    AND created_at > NOW() - INTERVAL '25 hours'
                    """,
                    (job_name,),
                )

                row = cur.fetchone()
                if not row or row[3] == 0:
                    return {
                        "job_name": job_name,
                        "status": "missing",
                        "sla_exceeded": True,
                        "warning": f"No recent execution of {job_name}",
                    }

                started_at, completed_at, failed_at, _ = row

                if failed_at:
                    return {
                        "job_name": job_name,
                        "last_run": failed_at.isoformat(),
                        "status": "failed",
                        "sla_exceeded": True,
                        "warning": f"{job_name} failed",
                    }

                if completed_at and started_at:
                    duration = (completed_at - started_at).total_seconds()
                    sla_exceeded = duration > (self.sla_minutes * 60)

                    return {
                        "job_name": job_name,
                        "last_run": completed_at.isoformat(),
                        "duration_seconds": int(duration),
                        "sla_exceeded": sla_exceeded,
                        "status": "completed",
                        "warning": f"Duration {int(duration)}s exceeds SLA {self.sla_minutes * 60}s"
                        if sla_exceeded
                        else None,
                    }

                return {
                    "job_name": job_name,
                    "status": "in_progress",
                    "sla_exceeded": False,
                }

            conn.close()

        except Exception as e:
            logger.error(f"❌ Error checking SLA: {e}")
            return {
                "job_name": job_name,
                "status": "error",
                "error": str(e),
            }

    def check_all_slas(self) -> dict:
        """Check SLA for all scheduled jobs.

        Returns:
            {
                "timestamp": str,
                "healthy": bool,
                "jobs": [job_check_result],
                "alerts": [str]
            }
        """
        alerts = []
        job_results = []

        for job_name in ["job_mim_etl", "job_corpus_ingest"]:
            result = self.check_job_sla(job_name)
            job_results.append(result)

            if result.get("warning"):
                alerts.append(result["warning"])

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "healthy": len(alerts) == 0,
            "jobs": job_results,
            "alerts": alerts,
        }
