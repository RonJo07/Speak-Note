#!/usr/bin/env python3
"""
Database Migration Script
Fixes the users table to support OTP-only users
"""

import asyncio
import logging
from sqlalchemy import text
from app.database import get_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_migration():
    """Run the database migration to fix hashed_password field"""
    
    async for db in get_db():
        try:
            logger.info("Starting database migration...")
            
            # Step 1: Update hashed_password to allow NULL
            logger.info("Updating hashed_password column to allow NULL...")
            await db.execute(text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL"))
            
            # Step 2: Add OTP columns if they don't exist
            logger.info("Checking for OTP columns...")
            
            # Check if otp column exists
            result = await db.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'otp'
            """))
            otp_exists = result.scalar() > 0
            
            if not otp_exists:
                logger.info("Adding otp column...")
                await db.execute(text("ALTER TABLE users ADD COLUMN otp VARCHAR"))
            else:
                logger.info("otp column already exists")
            
            # Check if otp_expires_at column exists
            result = await db.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'otp_expires_at'
            """))
            otp_expires_exists = result.scalar() > 0
            
            if not otp_expires_exists:
                logger.info("Adding otp_expires_at column...")
                await db.execute(text("ALTER TABLE users ADD COLUMN otp_expires_at TIMESTAMP WITH TIME ZONE"))
            else:
                logger.info("otp_expires_at column already exists")
            
            # Commit the changes
            await db.commit()
            logger.info("Migration completed successfully!")
            
            # Verify the changes
            logger.info("Verifying table structure...")
            result = await db.execute(text("""
                SELECT column_name, is_nullable, data_type
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            logger.info("Current table structure:")
            for column in columns:
                logger.info(f"  {column[0]}: {column[2]} (nullable: {column[1]})")
            
            break
            
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            await db.rollback()
            raise
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(run_migration()) 