#!/usr/bin/env python3
"""Test the actual middleware behavior after our fix."""

import asyncio
from app.core.modbus_client import ModbusClientManager
from app.config.devices import DEVICE_CONFIGS
from app.core.modbus_client import RegisterType


async def test_middleware_behavior():
    """Test the actual middleware behavior."""
    manager = ModbusClientManager(DEVICE_CONFIGS)
    
    try:
        print("--- Testing middleware behavior after fix ---")
        
        # Quick consecutive calls to see if we get consistent values
        for i in range(5):
            result = await manager.read_registers(
                device_id="rgv-lithium", 
                register_type=RegisterType.HOLDING, 
                address=15, 
                count=1
            )
            print(f"Call {i+1}: {result}")
            await asyncio.sleep(0.5)  # Small delay between calls
        
        print("\n--- Testing different counts ---")
        result1 = await manager.read_registers(
            device_id="rgv-lithium", 
            register_type=RegisterType.HOLDING, 
            address=15, 
            count=1
        )
        print(f"Count 1: {result1}")
        
        result2 = await manager.read_registers(
            device_id="rgv-lithium", 
            register_type=RegisterType.HOLDING, 
            address=15, 
            count=2
        )
        print(f"Count 2: {result2}")
        
        # Check if first values are consistent
        if result1 and result2:
            print(f"Consistency check - First value in count=1: {result1[0]}, First value in count=2: {result2[0]}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await manager.close_all()


if __name__ == "__main__":
    asyncio.run(test_middleware_behavior())