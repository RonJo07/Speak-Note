from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select
from datetime import datetime, timedelta
from app.models import User, Reminder, LoginHistory
from app.schemas import UserCreate, ReminderCreate, LoginHistoryCreate
from app.auth import get_password_hash, verify_password

# User CRUD operations
async def get_user_by_email(db: AsyncSession, email: str):
    """Get user by email"""
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user_data: UserCreate):
    """Create a new user"""
    # Handle empty password for OTP users
    if not user_data.password:
        # Create user without password for OTP-based registration
        db_user = User(
            email=user_data.email,
            hashed_password="",  # Empty string for OTP users
            full_name=user_data.full_name
        )
    else:
        # Create user with password
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

async def create_user_without_password(db: AsyncSession, email: str, full_name: str):
    """Create a new user without password (for OTP-based registration)"""
    db_user = User(
        email=email,
        hashed_password="",  # Empty string for OTP users
        full_name=full_name
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
    
    # Check if user has a password (OTP-only users won't have hashed_password)
    if not user.hashed_password:
        return None  # User exists but has no password (OTP-only user)
    
    if not verify_password(password, user.hashed_password):
        return None
    return user

async def set_user_otp(db: AsyncSession, user: User, otp: str):
    """Set OTP for a user with a 10-minute expiration."""
    user.otp = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.add(user)
    await db.commit()
    await db.refresh(user)

async def verify_user_otp(db: AsyncSession, email: str, otp: str):
    """Verify user's OTP."""
    user = await get_user_by_email(db, email)
    if not user or not user.otp or not user.otp_expires_at:
        return None
    
    if user.otp_expires_at < datetime.utcnow():
        # OTP has expired
        return None
    
    if user.otp != otp:
        return None
        
    # OTP is correct, clear it after use
    user.otp = None
    user.otp_expires_at = None
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user

async def create_login_history(db: AsyncSession, history_data: LoginHistoryCreate):
    """Create a new login history record"""
    db_history = LoginHistory(**history_data.dict())
    db.add(db_history)
    await db.commit()
    await db.refresh(db_history)
    return db_history

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

# Alias for main.py compatibility
async def update_reminder(db: AsyncSession, reminder_id: int, reminder_data: ReminderCreate, user_id: int):
    """Update a reminder (alias for update_reminder_by_id)"""
    return await update_reminder_by_id(db, reminder_id, reminder_data, user_id)

async def delete_reminder_by_id(db: AsyncSession, reminder_id: int, user_id: int):
    """Delete a reminder"""
    db_reminder = await get_reminder_by_id(db, reminder_id, user_id)
    if not db_reminder:
        return False
    
    await db.delete(db_reminder)
    await db.commit()
    return True

# Alias for main.py compatibility
async def delete_reminder(db: AsyncSession, reminder_id: int, user_id: int):
    """Delete a reminder (alias for delete_reminder_by_id)"""
    return await delete_reminder_by_id(db, reminder_id, user_id)

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

async def uncomplete_reminder(db: AsyncSession, reminder_id: int, user_id: int):
    """Mark a reminder as uncompleted"""
    db_reminder = await get_reminder_by_id(db, reminder_id, user_id)
    if not db_reminder:
        return None
    
    db_reminder.is_completed = False
    await db.commit()
    await db.refresh(db_reminder)
    return db_reminder

# Alias for main.py compatibility
async def complete_reminder(db: AsyncSession, reminder_id: int, user_id: int):
    """Mark a reminder as completed (alias for mark_reminder_completed)"""
    return await mark_reminder_completed(db, reminder_id, user_id) 