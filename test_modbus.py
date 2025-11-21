#!/usr/bin/env python3
"""Test script to verify Modbus register reading behavior after fix."""

import asyncio
from app.core.modbus_client import ModbusClientManager
from app.config.devices import DEVICE_CONFIGS
from app.core.modbus_client import RegisterType


async def test_modbus_read():
    """Test reading registers directly from the Modbus client after the fix."""
    manager = ModbusClientManager(DEVICE_CONFIGS)

    try:
        # Test reading a single register as in your issue
        result = await manager.read_registers(
            device_id="rgv-lithium",
            register_type=RegisterType.HOLDING,
            address=15,
            count=1
        )

        print(f"After fix - Reading 1 register from address 15: {result}")
        print(f"Length of result: {len(result)}")

        # Test with 2 registers to see if we get exactly 2
        result2 = await manager.read_registers(
            device_id="rgv-lithium",
            register_type=RegisterType.HOLDING,
            address=15,
            count=2
        )

        print(f"After fix - Reading 2 registers starting from address 15: {result2}")
        print(f"Length of result: {len(result2)}")

        # Test with 5 registers to see if we get exactly 5
        result3 = await manager.read_registers(
            device_id="rgv-lithium",
            register_type=RegisterType.HOLDING,
            address=15,
            count=5
        )

        print(f"After fix - Reading 5 registers starting from address 15: {result3}")
        print(f"Length of result: {len(result3)}")

    except Exception as e:
        print(f"Error during Modbus call: {e}")
    finally:
        await manager.close_all()


if __name__ == "__main__":
    asyncio.run(test_modbus_read())