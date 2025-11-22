#!/usr/bin/env python3
"""Debug script to understand Modbus device behavior."""

import asyncio
from app.core.modbus_client import ModbusClientManager, ModbusSession
from app.config.devices import DEVICE_CONFIGS
from app.core.modbus_client import RegisterType
from pymodbus.client import ModbusTcpClient


async def debug_modbus_device():
    """Debug Modbus device behavior to understand the exact response."""
    config = DEVICE_CONFIGS[0]  # rgv-lithium
    
    # Create a direct client connection to test
    client = ModbusTcpClient(
        host=config.host,
        port=config.port,
        timeout=config.timeout,
        framer=config.framer,
    )
    
    try:
        print("Connecting to Modbus device...")
        if client.connect():
            print("Connected successfully")
            
            # Test reading different counts and see what the raw response is
            print("\n--- Testing raw pymodbus calls ---")
            
            # Test 1: Request 1 register
            print("\nRequesting 1 register from address 15:")
            result1 = client.read_holding_registers(address=15, count=1, slave=config.slave_id)
            if not result1.isError():
                print(f"  Raw response registers: {result1.registers}")
                print(f"  Length: {len(result1.registers)}")
            else:
                print(f"  Error: {result1}")
            
            # Test 2: Request 2 registers
            print("\nRequesting 2 registers from address 15:")
            result2 = client.read_holding_registers(address=15, count=2, slave=config.slave_id)
            if not result2.isError():
                print(f"  Raw response registers: {result2.registers}")
                print(f"  Length: {len(result2.registers)}")
            else:
                print(f"  Error: {result2}")
                
            # Test 3: Request 5 registers
            print("\nRequesting 5 registers from address 15:")
            result5 = client.read_holding_registers(address=15, count=5, slave=config.slave_id)
            if not result5.isError():
                print(f"  Raw response registers: {result5.registers}")
                print(f"  Length: {len(result5.registers)}")
            else:
                print(f"  Error: {result5}")
                
            # Test other addresses to see if the pattern is consistent
            print("\n--- Testing other addresses ---")
            for addr in [10, 12, 14, 16, 17]:
                print(f"\nRequesting 1 register from address {addr}:")
                result = client.read_holding_registers(address=addr, count=1, slave=config.slave_id)
                if not result.isError():
                    print(f"  Raw response registers: {result.registers}")
                    print(f"  Length: {len(result.registers)}")
                else:
                    print(f"  Error: {result}")
                    
        else:
            print("Failed to connect")
    except Exception as e:
        print(f"Exception occurred: {e}")
    finally:
        if client.is_socket_open():
            client.close()


if __name__ == "__main__":
    asyncio.run(debug_modbus_device())