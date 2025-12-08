"""Migration 003: Add foreign key constraint to polling_targets.

Adds FK constraint from polling_targets.device_id to modbus_devices.device_id
for referential integrity.

Run from project root:
    python -m migrations.003_add_polling_target_fk
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.base import MigrationRunner


async def add_fk_constraint(session: AsyncSession) -> None:
    """Add foreign key constraint to polling_targets table."""
    
    runner = MigrationRunner("003_add_polling_target_fk")
    
    # Check if constraint already exists
    check_sql = text("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'polling_targets' 
        AND constraint_type = 'FOREIGN KEY'
        AND constraint_name = 'fk_polling_targets_device_id'
    """)
    
    result = await session.execute(check_sql)
    existing = result.scalar_one_or_none()
    
    if existing:
        runner.print_warning("FK constraint already exists. Skipping.")
        return
    
    # First, delete any orphan polling targets (those referencing non-existent devices)
    cleanup_sql = text("""
        DELETE FROM polling_targets 
        WHERE device_id NOT IN (SELECT device_id FROM modbus_devices)
    """)
    cleanup_result = await session.execute(cleanup_sql)
    if cleanup_result.rowcount > 0:
        runner.print_warning(f"Deleted {cleanup_result.rowcount} orphan polling target(s)")
    
    # Add the FK constraint
    alter_sql = text("""
        ALTER TABLE polling_targets 
        ADD CONSTRAINT fk_polling_targets_device_id 
        FOREIGN KEY (device_id) 
        REFERENCES modbus_devices(device_id) 
        ON DELETE CASCADE
    """)
    
    await session.execute(alter_sql)
    await session.commit()
    
    runner.print_success("Added FK constraint: polling_targets.device_id -> modbus_devices.device_id")


async def main():
    """Run migration."""
    runner = MigrationRunner("003_add_polling_target_fk")
    
    runner.print_header("Migration 003: Add Polling Target FK Constraint")
    runner.print_info("This migration adds referential integrity between polling_targets and modbus_devices")
    
    await runner.run(
        create_tables=False,
        seed_data=add_fk_constraint,
    )
    
    print("\nThis ensures:")
    print("  • Polling targets can only reference existing devices")
    print("  • Deleting a device will auto-delete its polling targets (CASCADE)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
