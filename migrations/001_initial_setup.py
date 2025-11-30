"""Migration 001: Initial database setup with modbus_devices table.

Creates the modbus_devices table and seeds initial device configurations.

Run from project root:
    python -m migrations.001_initial_setup
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import ModbusDevice
from migrations.base import MigrationRunner


async def seed_initial_devices(session: AsyncSession) -> None:
    """Seed initial Modbus device configurations."""
    
    runner = MigrationRunner("001_initial_setup")
    
    # Check if devices already exist
    existing = await crud.get_all_devices(session)
    if existing:
        runner.print_warning(
            f"Devices already exist ({len(existing)} found). Skipping seed data."
        )
        return
    
    # Sample devices matching hardcoded DEVICE_CONFIGS
    sample_devices = [
        ModbusDevice(
            device_id="office-eng",
            host="10.19.20.148",
            port=8899,
            slave_id=1,
            timeout=10,
            framer="RTU",
            max_retries=5,
            retry_delay=0.1,
            is_active=True,
        ),
        ModbusDevice(
            device_id="formation",
            host="10.19.20.148",
            port=8899,
            slave_id=2,
            timeout=10,
            framer="RTU",
            max_retries=5,
            retry_delay=0.1,
            is_active=True,
        ),
    ]
    
    for device in sample_devices:
        await crud.create_device(session, device)
        runner.print_success(
            f"Created device: {device.device_id} ({device.host}:{device.port}, slave={device.slave_id})"
        )


async def main():
    """Run migration."""
    runner = MigrationRunner("001_initial_setup")
    
    runner.print_header("Migration 001: Initial Setup")
    runner.print_info("This migration creates the modbus_devices table")
    
    await runner.run(
        create_tables=True,
        seed_data=seed_initial_devices,
    )
    
    print("\nNext steps:")
    print("  1. View devices: GET http://localhost:8000/api/admin/devices")
    print("  2. Create device: POST http://localhost:8000/api/admin/devices")
    print("  3. Reload configs: POST http://localhost:8000/api/admin/devices/reload")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
