"""Migration 002: Add polling_targets table.

Creates the polling_targets table and seeds initial polling configurations.

Run from project root:
    python -m migrations.002_add_polling_targets
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import PollingTarget
from migrations.base import MigrationRunner


async def seed_polling_targets(session: AsyncSession) -> None:
    """Seed initial polling target configurations."""
    
    runner = MigrationRunner("002_add_polling_targets")
    
    # Check if polling targets already exist
    existing = await crud.get_all_polling_targets(session)
    if existing:
        runner.print_warning(
            f"Polling targets already exist ({len(existing)} found). Skipping seed data."
        )
        return
    
    # Sample polling targets
    sample_targets = [
        PollingTarget(
            device_id="office-eng",
            register_type="holding",
            address=0,
            count=10,
            description="Poll first 10 holding registers from office-eng device",
            is_active=True,
        ),
        PollingTarget(
            device_id="formation",
            register_type="input",
            address=0,
            count=5,
            description="Poll first 5 input registers from formation device",
            is_active=True,
        ),
    ]
    
    for target in sample_targets:
        # Check if device exists first
        device = await crud.get_device(session, target.device_id)
        if device:
            await crud.create_polling_target(session, target)
            runner.print_success(
                f"Created polling target: {target.device_id} {target.register_type} "
                f"addr={target.address} count={target.count}"
            )
        else:
            runner.print_warning(
                f"Skipping target for '{target.device_id}' - device not found in database"
            )


async def main():
    """Run migration."""
    runner = MigrationRunner("002_add_polling_targets")
    
    runner.print_header("Migration 002: Add Polling Targets")
    runner.print_info("This migration creates the polling_targets table")
    
    await runner.run(
        create_tables=True,
        seed_data=seed_polling_targets,
    )
    
    print("\nNext steps:")
    print("  1. View polling targets: GET http://localhost:8000/api/admin/polling")
    print("  2. Create new target:    POST http://localhost:8000/api/admin/polling")
    print("  3. Update target:        PUT http://localhost:8000/api/admin/polling/{id}")
    print("  4. Delete target:        DELETE http://localhost:8000/api/admin/polling/{id}")
    print("\nPolling service will automatically reload targets from database every 5 seconds.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
