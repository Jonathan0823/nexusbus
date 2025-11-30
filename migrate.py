"""Run all database migrations.

This script runs all migrations in order to set up the complete database schema.

Usage:
    python migrate.py                    # Run all migrations
    python migrate.py --migration 001    # Run specific migration only
"""

import argparse
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def run_all_migrations():
    """Run all migrations in order."""
    from migrations import __001_initial_setup, __002_add_polling_targets
    
    print("=" * 70)
    print("  Running All Migrations")
    print("=" * 70)
    
    # Migration 001: Initial setup
    print("\n📦 Running Migration 001: Initial Setup...")
    await __001_initial_setup.main()
    
    # Migration 002: Polling targets
    print("\n📦 Running Migration 002: Add Polling Targets...")
    await __002_add_polling_targets.main()
    
    print("\n" + "=" * 70)
    print("  ✨ All Migrations Completed Successfully!")
    print("=" * 70)


async def run_single_migration(migration_number: str):
    """Run a specific migration."""
    migrations = {
        "001": ("Initial Setup", "migrations.001_initial_setup"),
        "002": ("Add Polling Targets", "migrations.002_add_polling_targets"),
    }
    
    if migration_number not in migrations:
        print(f"❌ Unknown migration: {migration_number}")
        print(f"Available migrations: {', '.join(migrations.keys())}")
        return
    
    name, module_path = migrations[migration_number]
    print(f"📦 Running Migration {migration_number}: {name}...")
    
    # Dynamically import and run the migration
    module = __import__(module_path, fromlist=['main'])
    await module.main()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument(
        "--migration",
        type=str,
        help="Run specific migration (e.g., 001, 002)",
        default=None,
    )
    
    args = parser.parse_args()
    
    if args.migration:
        asyncio.run(run_single_migration(args.migration))
    else:
        asyncio.run(run_all_migrations())


if __name__ == "__main__":
    main()
