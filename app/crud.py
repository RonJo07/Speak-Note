from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select
from datetime import datetime, timedelta
from app.models import User, Reminder
from app.schemas import UserCreate, ReminderCreate
from app.auth import get_password_hash, verify_password

# User CRUD operations
async def get_user_by_email(db: AsyncSession, email: str):
    """Get user by email"""
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user_data: UserCreate):
    """Create a new user"""
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def authenticate_user(db: AsyncSession, email: str, password: str):
    """Authenticate user with email and password"""
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

# Reminder CRUD operations
async def create_reminder(db: AsyncSession, reminder_data: ReminderCreate, user_id: int):
    """Create a new reminder"""
    db_reminder = Reminder(
        **reminder_data.dict(),
        user_id=user_id
    )
    db.add(db_reminder)
    await db.commit()
    await db.refresh(db_reminder)
    return db_reminder

async def get_user_reminders(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100):
    """Get all reminders for a user"""
    result = await db.execute(
        select(Reminder).filter(Reminder.user_id == user_id).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def get_reminder_by_id(db: AsyncSession, reminder_id: int, user_id: int):
    """Get a specific reminder by ID for a user"""
    result = await db.execute(
        select(Reminder).filter(
            and_(Reminder.id == reminder_id, Reminder.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()

async def update_reminder_by_id(db: AsyncSession, reminder_id: int, reminder_data: ReminderCreate, user_id: int):
    """Update a reminder"""
    db_reminder = await get_reminder_by_id(db, reminder_id, user_id)
    if not db_reminder:
        return None
    
    for key, value in reminder_data.dict().items():
        setattr(db_reminder, key, value)
    
    await db.commit()
    await db.refresh(db_reminder)
    return db_reminder

async def delete_reminder_by_id(db: AsyncSession, reminder_id: int, user_id: int):
    """Delete a reminder"""
    db_reminder = await get_reminder_by_id(db, reminder_id, user_id)
    if not db_reminder:
        return False
    
    await db.delete(db_reminder)
    await db.commit()
    return True

async def get_upcoming_reminders(db: AsyncSession, user_id: int, days: int = 7):
    """Get upcoming reminders for the next N days"""
    end_date = datetime.utcnow() + timedelta(days=days)
    result = await db.execute(
        select(Reminder).filter(
            and_(
                Reminder.user_id == user_id,
                Reminder.scheduled_for >= datetime.utcnow(),
                Reminder.scheduled_for <= end_date,
                Reminder.is_completed == False
            )
        ).order_by(Reminder.scheduled_for)
    )
    return result.scalars().all()

async def mark_reminder_completed(db: AsyncSession, reminder_id: int, user_id: int):
    """Mark a reminder as completed"""
    db_reminder = await get_reminder_by_id(db, reminder_id, user_id)
    if not db_reminder:
        return None
    
    db_reminder.is_completed = True
    await db.commit()
    await db.refresh(db_reminder)
    return db_reminder 