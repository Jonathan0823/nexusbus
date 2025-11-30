# Database Migrations

> **Database migration scripts for the Modbus Middleware project**

**[← Main README](../README.md)** | **[Setup Guide](../DATABASE_SETUP.md)** | **[Device API](../docs/DEVICE_MANAGEMENT.md)** | **[Polling](../docs/POLLING_CONFIGURATION.md)**

---

## 📚 Quick Navigation

- [Directory Structure](#directory-structure)
- [Running Migrations](#running-migrations)
- [Migration Details](#migration-details)
- [Creating New Migrations](#creating-new-migrations)
- [Troubleshooting](#troubleshooting)

---

## Directory Structure

```
migrations/
├── __init__.py                    # Package initialization
├── base.py                        # Base migration utilities
├── 001_initial_setup.py          # Create modbus_devices table
└── 002_add_polling_targets.py    # Create polling_targets table
```

## Running Migrations

### Run All Migrations

From the project root directory:

```bash
python migrate.py
```

This will run all migrations in order:
1. Create `modbus_devices` table
2. Create `polling_targets` table
3. Seed initial data for both tables

### Run Specific Migration

```bash
# Run only initial setup
python migrate.py --migration 001

# Run only polling targets
python migrate.py --migration 002
```

### Run Individual Migration Directly

```bash
# Migration 001
python -m migrations.001_initial_setup

# Migration 002
python -m migrations.002_add_polling_targets
```

## Migration Details

### 001: Initial Setup

**Creates**: `modbus_devices` table

**Schema**:
```sql
CREATE TABLE modbus_devices (
    device_id VARCHAR(50) PRIMARY KEY,
    host VARCHAR(100) NOT NULL,
    port INTEGER NOT NULL,
    slave_id INTEGER NOT NULL,
    timeout INTEGER DEFAULT 10,
    framer VARCHAR(20) DEFAULT 'RTU',
    max_retries INTEGER DEFAULT 5,
    retry_delay FLOAT DEFAULT 0.1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Seed Data**:
- `office-eng` device (10.19.20.148:8899, slave_id=1)
- `formation` device (10.19.20.148:8899, slave_id=2)

### 002: Add Polling Targets

**Creates**: `polling_targets` table

**Schema**:
```sql
CREATE TABLE polling_targets (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    register_type VARCHAR(20) NOT NULL,
    address INTEGER NOT NULL,
    count INTEGER DEFAULT 1 CHECK (count >= 1 AND count <= 125),
    is_active BOOLEAN DEFAULT TRUE,
    description VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_polling_targets_device_id ON polling_targets(device_id);
```

**Seed Data**:
- Poll office-eng holding registers (addr=0, count=10)
- Poll formation input registers (addr=0, count=5)

## Creating New Migrations

### Step 1: Create Migration File

Create a new file `migrations/00X_description.py`:

```python
"""Migration 00X: Description of what this migration does.

Run from project root:
    python -m migrations.00X_description
"""

from sqlalchemy.ext.asyncio import AsyncSession
from migrations.base import MigrationRunner


async def seed_data(session: AsyncSession) -> None:
    """Seed data for this migration."""
    runner = MigrationRunner("00X_description")
    
    # Your seed logic here
    runner.print_success("Data seeded successfully")


async def main():
    """Run migration."""
    runner = MigrationRunner("00X_description")
    
    runner.print_header("Migration 00X: Description")
    runner.print_info("What this migration does...")
    
    await runner.run(
        create_tables=True,
        seed_data=seed_data,
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Step 2: Update migrate.py

Add your migration to the `migrations` dict in `migrate.py`:

```python
migrations = {
    "001": ("Initial Setup", "migrations.001_initial_setup"),
    "002": ("Add Polling Targets", "migrations.002_add_polling_targets"),
    "00X": ("Your Description", "migrations.00X_description"),  # Add this
}
```

### Step 3: Update run_all_migrations()

Add your migration to the sequence in `migrate.py`:

```python
async def run_all_migrations():
    from migrations import __001_initial_setup, __002_add_polling_targets, __00X_description
    
    # ... existing migrations ...
    
    print("\n📦 Running Migration 00X: Your Description...")
    await __00X_description.main()
```

## Migration Best Practices

1. **Idempotent**: Migrations should be safe to run multiple times
2. **Check Existence**: Always check if data exists before seeding
3. **Logging**: Use the `MigrationRunner` helper for consistent logging
4. **Ordering**: Number migrations sequentially (001, 002, 003, ...)
5. **Documentation**: Document what each migration does at the top
6. **Rollback**: Keep manual rollback SQL scripts if needed

## Troubleshooting

### Migration Already Run

If you get warnings about existing data, it's safe - migrations are idempotent:

```
⚠️  Devices already exist (2 found). Skipping seed data.
```

### Database Connection Error

Ensure your `.env` file is configured:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/modbus_db
```

### Import Errors

Run migrations from the project root directory:

```bash
cd d:/coding/modbus_middleware
python migrate.py
```

## Verification

After running migrations, verify the database:

```bash
# Check devices
curl http://localhost:8000/api/admin/devices

# Check polling targets
curl http://localhost:8000/api/admin/polling
```

## Rollback

Migrations don't have automatic rollback. To rollback:

1. Drop tables manually via SQL
2. Re-run migrations

Or use a database admin tool to manage schema.
