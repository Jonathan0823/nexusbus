"""Migration 004: Add device_health table for tracking device health and quarantine state.

Creates the device_health table with columns:
- device_id (PK, FK to modbus_devices)
- state (healthy/degraded/offline)
- failure_count, consecutive_failures, success_count
- last_success, last_failure (timestamps)
- quarantine_until (timestamp for quarantine expiry)
- created_at, updated_at

Run from project root:
    python -m migrations.004_add_device_health
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.base import MigrationRunner


async def create_device_health_table(session: AsyncSession) -> None:
    """Create the device_health table."""
    
    runner = MigrationRunner("004_add_device_health")
    runner.print_info("Creating device_health table...")
    
    # Check if table already exists
    check_sql = text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name = 'device_health'
    """)
    
    result = await session.execute(check_sql)
    existing = result.scalar_one_or_none()
    
    if existing:
        runner.print_warning("device_health table already exists. Skipping.")
        return
    
    # Create the device_health table
    create_sql = text("""
        CREATE TABLE device_health (
            device_id VARCHAR(50) PRIMARY KEY,
            state VARCHAR(20) NOT NULL DEFAULT 'healthy',
            failure_count INTEGER NOT NULL DEFAULT 0,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            last_success TIMESTAMP WITH TIME ZONE NULL,
            last_failure TIMESTAMP WITH TIME ZONE NULL,
            quarantine_until TIMESTAMP WITH TIME ZONE NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_device_health_device 
                FOREIGN KEY (device_id) 
                REFERENCES modbus_devices(device_id) 
                ON DELETE CASCADE
        )
    """)
    
    await session.execute(create_sql)
    
    # Create index on state for faster queries
    await session.execute(text("CREATE INDEX idx_device_health_state ON device_health(state)"))
    
    # Create index on quarantine_until for efficient quarantine filtering
    await session.execute(text("CREATE INDEX idx_device_health_quarantine ON device_health(quarantine_until)"))
    
    await session.commit()
    
    runner.print_success("Created device_health table with indexes")
    runner.print_info("  - PK: device_id (FK -> modbus_devices)")
    runner.print_info("  - Indexes: state, quarantine_until")
    
    # Populate initial health records for existing devices
    runner.print_info("Populating initial health records for existing devices...")
    
    populate_sql = text("""
        INSERT INTO device_health (device_id, state, failure_count, consecutive_failures, 
                                   success_count, created_at, updated_at)
        SELECT 
            device_id, 
            'healthy'::VARCHAR, 
            0, 
            0, 
            0, 
            NOW(), 
            NOW()
        FROM modbus_devices 
        WHERE device_id NOT IN (SELECT device_id FROM device_health)
        ON CONFLICT (device_id) DO NOTHING
    """)
    
    await session.execute(populate_sql)
    await session.commit()
    
    runner.print_success("Initial health records created for existing devices")


async def main():
    """Run migration."""
    runner = MigrationRunner("004_add_device_health")
    
    runner.print_header("Migration 004: Add Device Health Table")
    runner.print_info("This migration creates the device_health table for tracking")
    runner.print_info("device health states, failure counts, and quarantine periods.")
    runner.print_info("")
    runner.print_info("Benefits:")
    runner.print_info("  • Prevents one bad device from poisoning shared gateway")
    runner.print_info("  • Exponential backoff quarantine (15s→30s→60s→300s cap)")
    runner.print_info("  • Health-aware polling (quarantined devices skipped)")
    runner.print_info("  • Per-device failure tracking with circuit breaker pattern")
    
    await runner.run(
        create_tables=True,  # Ensures modbus_devices exists first
        seed_data=create_device_health_table,
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
