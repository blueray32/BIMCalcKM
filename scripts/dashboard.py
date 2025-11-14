#!/usr/bin/env python
"""
BIMCalc Pipeline Dashboard - Quick system overview
Usage: python scripts/dashboard.py
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


def get_db_stats():
    """Get database statistics."""
    db_path = Path("bimcalc.db")

    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    stats = {}

    # Database size
    stats["db_size"] = db_path.stat().st_size

    # Total BIM items
    cursor.execute("SELECT COUNT(*) FROM items")
    stats["bim_items"] = cursor.fetchone()[0]

    # Total price items (all history)
    cursor.execute("SELECT COUNT(*) FROM price_items")
    stats["price_items_total"] = cursor.fetchone()[0]

    # Current price items only
    cursor.execute("SELECT COUNT(*) FROM price_items WHERE is_current = 1")
    stats["price_items_current"] = cursor.fetchone()[0]

    # Expired price items (historical)
    stats["price_items_historical"] = (
        stats["price_items_total"] - stats["price_items_current"]
    )

    # Total mappings
    cursor.execute("SELECT COUNT(*) FROM item_mapping")
    stats["mappings"] = cursor.fetchone()[0]

    # Active mappings
    cursor.execute(
        "SELECT COUNT(*) FROM item_mapping WHERE end_ts IS NULL"
    )
    stats["mappings_active"] = cursor.fetchone()[0]

    # Price items by region
    cursor.execute(
        """
        SELECT region, COUNT(*) as count
        FROM price_items
        WHERE is_current = 1
        GROUP BY region
        ORDER BY count DESC
    """
    )
    stats["regions"] = cursor.fetchall()

    # Price items by classification
    cursor.execute(
        """
        SELECT classification_code, COUNT(*) as count
        FROM price_items
        WHERE is_current = 1
        GROUP BY classification_code
        ORDER BY count DESC
        LIMIT 10
    """
    )
    stats["classifications"] = cursor.fetchall()

    # Recent price changes (last 7 days)
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM price_items
        WHERE valid_from >= datetime('now', '-7 days')
        AND is_current = 1
    """
    )
    stats["recent_changes"] = cursor.fetchone()[0]

    # Pipeline runs
    cursor.execute("SELECT COUNT(*) FROM data_sync_log")
    stats["pipeline_runs"] = cursor.fetchone()[0]

    # Recent pipeline runs (last 24 hours)
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM data_sync_log
        WHERE run_timestamp >= datetime('now', '-1 day')
    """
    )
    stats["recent_runs"] = cursor.fetchone()[0]

    # Failed runs (last 7 days)
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM data_sync_log
        WHERE run_timestamp >= datetime('now', '-7 days')
        AND status = 'FAILED'
    """
    )
    stats["recent_failures"] = cursor.fetchone()[0]

    # Last pipeline run
    cursor.execute(
        """
        SELECT
            datetime(run_timestamp) as run_time,
            source_name,
            status,
            records_inserted + records_updated as records_processed,
            duration_seconds
        FROM data_sync_log
        ORDER BY run_timestamp DESC
        LIMIT 1
    """
    )
    last_run = cursor.fetchone()
    if last_run:
        stats["last_run"] = {
            "timestamp": last_run[0],
            "source": last_run[1],
            "status": last_run[2],
            "records": last_run[3],
            "duration": last_run[4],
        }
    else:
        stats["last_run"] = None

    # Price volatility (items with multiple price changes)
    cursor.execute(
        """
        SELECT item_code, region, COUNT(*) as changes
        FROM price_items
        GROUP BY item_code, region
        HAVING COUNT(*) > 1
        ORDER BY changes DESC
        LIMIT 5
    """
    )
    stats["volatile_items"] = cursor.fetchall()

    # Average price by classification
    cursor.execute(
        """
        SELECT classification_code, AVG(unit_price) as avg_price, currency
        FROM price_items
        WHERE is_current = 1
        GROUP BY classification_code, currency
        ORDER BY avg_price DESC
        LIMIT 5
    """
    )
    stats["avg_prices"] = cursor.fetchall()

    conn.close()
    return stats


def format_size(bytes):
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"


def format_duration(seconds):
    """Format duration in seconds to human readable."""
    if seconds is None:
        return "N/A"
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds / 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def print_dashboard():
    """Print dashboard to console."""
    print("\n")
    print("=" * 70)
    print("                    BIMCalc Pipeline Dashboard")
    print("=" * 70)
    print()

    stats = get_db_stats()

    if not stats:
        print("❌ Database not found (bimcalc.db)")
        print("   Run: python -m bimcalc.cli init")
        return

    # System Overview
    print("📊 SYSTEM OVERVIEW")
    print("-" * 70)
    print(f"  Database Size:        {format_size(stats['db_size'])}")
    print(f"  BIM Items:            {stats['bim_items']:,}")
    print(
        f"  Price Items:          {stats['price_items_current']:,} current / "
        f"{stats['price_items_historical']:,} historical"
    )
    print(
        f"  Mappings:             {stats['mappings_active']:,} active / "
        f"{stats['mappings']:,} total"
    )
    print()

    # Pipeline Status
    print("⚙️  PIPELINE STATUS")
    print("-" * 70)
    print(f"  Total Runs:           {stats['pipeline_runs']:,}")
    print(f"  Runs (24h):           {stats['recent_runs']}")
    print(f"  Failures (7d):        {stats['recent_failures']}")

    if stats["last_run"]:
        lr = stats["last_run"]
        print(f"  Last Run:             {lr['timestamp']}")
        print(f"    Source:             {lr['source']}")
        status_icon = "✅" if lr["status"] == "SUCCESS" else "❌"
        print(f"    Status:             {status_icon} {lr['status']}")
        print(f"    Records Processed:  {lr['records']}")
        print(f"    Duration:           {format_duration(lr['duration'])}")
    else:
        print("  Last Run:             None")

    print()

    # Price Data Overview
    print("💰 PRICE DATA")
    print("-" * 70)
    print(f"  Price Changes (7d):   {stats['recent_changes']}")

    if stats["regions"]:
        print("  By Region:")
        for region, count in stats["regions"]:
            print(f"    {region:>6s}:  {count:>6,} items")

    print()

    # Top Classifications
    if stats["classifications"]:
        print("  Top Classifications:")
        for code, count in stats["classifications"][:5]:
            print(f"    {code:>6}:  {count:>6,} items")
        print()

    # Price Volatility
    if stats["volatile_items"]:
        print("📈 MOST VOLATILE ITEMS (Most Price Changes)")
        print("-" * 70)
        for item_code, region, changes in stats["volatile_items"]:
            print(f"  {item_code:<20} ({region})  {changes} changes")
        print()

    # Average Prices
    if stats["avg_prices"]:
        print("💵 AVERAGE PRICES BY CLASSIFICATION")
        print("-" * 70)
        for code, avg_price, currency in stats["avg_prices"]:
            print(f"  {code:>6}:  {currency} {avg_price:>10.2f}")
        print()

    # Health Check
    print("🏥 HEALTH CHECK")
    print("-" * 70)

    health_ok = True

    # Check if pipeline has run recently
    if stats["last_run"]:
        last_run_time = datetime.fromisoformat(stats["last_run"]["timestamp"])
        hours_since = (datetime.now() - last_run_time).total_seconds() / 3600

        if hours_since > 48:
            print(f"  ⚠️  Pipeline hasn't run in {hours_since:.0f} hours")
            health_ok = False
        else:
            print(f"  ✅ Pipeline ran {hours_since:.1f} hours ago")

        if stats["last_run"]["status"] != "SUCCESS":
            print(f"  ⚠️  Last pipeline run failed: {stats['last_run']['status']}")
            health_ok = False
    else:
        print("  ⚠️  Pipeline has never run")
        health_ok = False

    # Check for recent failures
    if stats["recent_failures"] > 0:
        print(f"  ⚠️  {stats['recent_failures']} failures in last 7 days")
        health_ok = False
    else:
        print("  ✅ No failures in last 7 days")

    # Check database size growth
    if stats["db_size"] > 100 * 1024 * 1024:  # 100 MB
        print(
            f"  ⚠️  Database is large ({format_size(stats['db_size'])}) - "
            "consider archiving old data"
        )
    else:
        print(f"  ✅ Database size is healthy ({format_size(stats['db_size'])})")

    print()

    if health_ok:
        print("✅ OVERALL STATUS: HEALTHY")
    else:
        print("⚠️  OVERALL STATUS: NEEDS ATTENTION")

    print()
    print("=" * 70)
    print()

    # Quick action suggestions
    print("💡 QUICK ACTIONS")
    print("-" * 70)
    print("  View pipeline history:     python -m bimcalc.cli pipeline-status --last 10")
    print("  Run pipeline:              python -m bimcalc.cli sync-prices")
    print("  Check configuration:       python scripts/validate_config.py")
    print("  Create backup:             ./scripts/backup_database.sh")
    print("  Health check:              ./scripts/health_check.sh")
    print()


if __name__ == "__main__":
    try:
        print_dashboard()
    except Exception as e:
        print(f"❌ Error generating dashboard: {e}")
        import traceback

        traceback.print_exc()
