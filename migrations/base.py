"""Base utilities for database migrations."""

import asyncio
import logging
from typing import Callable, Awaitable

from app.database.connection import create_db_and_tables, async_session_maker

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Helper class to run database migrations."""
    
    def __init__(self, migration_name: str):
        self.migration_name = migration_name
        self.logger = logging.getLogger(f"migrations.{migration_name}")
    
    def print_header(self, title: str):
        """Print formatted migration header."""
        separator = "=" * 70
        print(f"\n{separator}")
        print(f"  {title}")
        print(separator)
    
    def print_success(self, message: str):
        """Print success message."""
        print(f"✅ {message}")
        self.logger.info(message)
    
    def print_warning(self, message: str):
        """Print warning message."""
        print(f"⚠️  {message}")
        self.logger.warning(message)
    
    def print_error(self, message: str):
        """Print error message."""
        print(f"❌ {message}")
        self.logger.error(message)
    
    def print_info(self, message: str):
        """Print info message."""
        print(f"ℹ️  {message}")
        self.logger.info(message)
    
    async def run(
        self,
        create_tables: bool = True,
        seed_data: Callable[[], Awaitable[None]] | None = None,
    ):
        """Run migration.
        
        Args:
            create_tables: Whether to create database tables
            seed_data: Async function to seed initial data
        """
        self.print_header(f"Migration: {self.migration_name}")
        
        try:
            # Create tables
            if create_tables:
                self.print_info("Creating/updating database tables...")
                await create_db_and_tables()
                self.print_success("Database tables created/updated")
            
            # Seed data
            if seed_data:
                self.print_info("Seeding initial data...")
                async with async_session_maker() as session:
                    await seed_data(session)
                self.print_success("Initial data seeded")
            
            self.print_header("Migration Completed Successfully! ✨")
            
        except Exception as e:
            self.print_error(f"Migration failed: {e}")
            raise


def run_migration(
    migration_name: str,
    create_tables: bool = True,
    seed_data: Callable | None = None,
):
    """Convenience function to run a migration.
    
    Args:
        migration_name: Name of the migration
        create_tables: Whether to create database tables
        seed_data: Async function to seed initial data
    """
    runner = MigrationRunner(migration_name)
    asyncio.run(runner.run(create_tables=create_tables, seed_data=seed_data))
