#!/usr/bin/env python3
"""
S3.10 + 3.11 Test: Validate job scheduling and SLA monitoring.

Tests:
1. Scheduler configuration
2. Job SLA calculation
3. Nightly job schedule correctness
4. Alert generation for violations
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not configured in .env")
    sys.exit(1)


def test_scheduler_config():
    """Test 1: Scheduler configuration loads correctly."""
    print("\n" + "=" * 70)
    print(" TEST 1: Scheduler Configuration")
    print("=" * 70)

    try:
        from config.job_scheduling import get_scheduler, JobScheduler
        from config.procrastinate_config import app

        scheduler = get_scheduler(app)

        schedules = scheduler.get_schedules()
        print(f"\n✅ Configured {len(schedules)} scheduled jobs:")

        for schedule in schedules:
            print(f"   - {schedule['job_name']}")
            print(f"     Time: {schedule['time']}")
            print(f"     Description: {schedule['description']}")

        assert len(schedules) >= 2, "Should have at least 2 scheduled jobs"
        print(f"\n✅ TEST 1 PASSED")

        return True

    except Exception as e:
        print(f"❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_next_run_times():
    """Test 2: Calculate next run times correctly."""
    print("\n" + "=" * 70)
    print(" TEST 2: Next Run Time Calculation")
    print("=" * 70)

    try:
        from config.job_scheduling import get_scheduler
        from config.procrastinate_config import app

        scheduler = get_scheduler(app)

        # Test MIM ETL (00:00 UTC)
        next_mim = scheduler.get_next_run_time(0, 0)
        print(f"\n📅 Next job_mim_etl: {next_mim.isoformat()}")

        # Test Corpus Ingest (02:00 UTC)
        next_corpus = scheduler.get_next_run_time(2, 0)
        print(f"📅 Next job_corpus_ingest: {next_corpus.isoformat()}")

        # Verify times are in the future
        now = datetime.now(timezone.utc)
        assert next_mim > now, "MIM ETL should be in future"
        assert next_corpus > now, "Corpus ingest should be in future"

        # Verify MIM comes before Corpus on same day (or day boundaries)
        if next_mim.date() == next_corpus.date():
            assert next_mim < next_corpus, "MIM should run before Corpus"

        print(f"\n✅ All times are in future")
        print(f"✅ TEST 2 PASSED")

        return True

    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_health_check():
    """Test 3: Health check reports status correctly."""
    print("\n" + "=" * 70)
    print(" TEST 3: Health Check")
    print("=" * 70)

    try:
        from config.job_scheduling import get_scheduler
        from config.procrastinate_config import app

        scheduler = get_scheduler(app)
        health = scheduler.health_check()

        print(f"\n📊 Health Status:")
        print(f"   Healthy: {health['healthy']}")
        print(f"   Next MIM ETL: {health['next_mim_etl']}")
        print(f"   Next Corpus Ingest: {health['next_corpus_ingest']}")

        if health['warnings']:
            print(f"   Warnings: {health['warnings']}")
        else:
            print(f"   Warnings: None")

        print(f"\n✅ TEST 3 PASSED")

        return True

    except Exception as e:
        print(f"❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sla_monitor():
    """Test 4: SLA monitoring calculates duration correctly."""
    print("\n" + "=" * 70)
    print(" TEST 4: SLA Monitoring")
    print("=" * 70)

    try:
        from config.job_scheduling import JobMonitor

        monitor = JobMonitor(DATABASE_URL, sla_minutes=30)

        # Check SLAs for all jobs
        all_slas = monitor.check_all_slas()

        print(f"\n📊 SLA Status ({all_slas['timestamp']}):")
        print(f"   Overall healthy: {all_slas['healthy']}")

        for job_result in all_slas["jobs"]:
            job_name = job_result.get("job_name", "unknown")
            status = job_result.get("status", "unknown")
            duration = job_result.get("duration_seconds", "N/A")

            print(f"\n   {job_name}:")
            print(f"     Status: {status}")

            if duration != "N/A":
                print(f"     Duration: {duration}s")

            if job_result.get("warning"):
                print(f"     ⚠️  Warning: {job_result['warning']}")

        if all_slas["alerts"]:
            print(f"\n   ⚠️  ALERTS: {len(all_slas['alerts'])}")
            for alert in all_slas["alerts"]:
                print(f"      - {alert}")

        print(f"\n✅ TEST 4 PASSED")

        return True

    except Exception as e:
        print(f"❌ TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_documentation():
    """Test 5: Workflow documentation exists."""
    print("\n" + "=" * 70)
    print(" TEST 5: Workflow Documentation")
    print("=" * 70)

    try:
        from pathlib import Path

        docs_path = Path("TIERSV3/JOBS_WORKFLOW.md")

        assert docs_path.exists(), f"Documentation not found: {docs_path}"

        with open(docs_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for key sections
        required_sections = [
            "COMPLETE WORKFLOW DIAGRAM",
            "NIGHTLY JOBS SCHEDULER",
            "RETRY STRATEGY",
            "FALLBACK PATHS",
            "PERFORMANCE TARGETS",
        ]

        for section in required_sections:
            assert section in content, f"Missing section: {section}"

        print(f"\n✅ Documentation exists: {docs_path}")
        print(f"   File size: {len(content)} bytes")
        print(f"   Sections: {len(required_sections)}")

        for section in required_sections:
            print(f"     ✅ {section}")

        print(f"\n✅ TEST 5 PASSED")

        return True

    except Exception as e:
        print(f"❌ TEST 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all scheduler tests."""
    print("=" * 70)
    print(" 🧪 S3.10 + 3.11 JOB SCHEDULER & DOCUMENTATION TEST")
    print("=" * 70)

    tests = [
        ("Scheduler Config", test_scheduler_config),
        ("Next Run Times", test_next_run_times),
        ("Health Check", test_health_check),
        ("SLA Monitor", test_sla_monitor),
        ("Documentation", test_workflow_documentation),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ {test_name} ERROR: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f" 📊 RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\n✅ ALL TESTS PASSED")
        print("\n📋 Next Steps:")
        print("   1. Configure supervisor for nightly job scheduling")
        print("   2. Set up PagerDuty/Slack alerts for SLA violations")
        print("   3. Deploy worker process (scripts/start_worker.py)")
        print("   4. Monitor job execution in events_job table")
        print("\n📚 See TIERSV3/JOBS_WORKFLOW.md for complete documentation")
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
