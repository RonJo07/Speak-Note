from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import uvicorn
import os
from typing import Optional, List
import json
from datetime import datetime, timedelta
import asyncio
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import engine, get_db, create_tables
from app.models import Base, Reminder, User
from app.schemas import ReminderCreate, ReminderResponse, UserCreate, UserResponse, LoginHistoryCreate
from app.ai_analysis import (
    analyze_voice_input,
    analyze_text_input,
    analyze_image_input,
    extract_scheduling_info
)
from app.auth import get_current_user, create_access_token
from app.config import settings

app = FastAPI(
    title="SpeakNote Remind API",
    description="AI-powered reminder application with voice, text, and image analysis",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://speak-note.vercel.app",  # Production frontend
        "https://speaknote-remind-frontend.vercel.app",  # Alternative production domain
        "https://speaknote-remind.vercel.app",  # Another possible domain
        "http://localhost:3000",  # Development frontend
        "http://127.0.0.1:3000"   # Alternative development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    await create_tables()

# Mount static files for uploaded images
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
async def root():
    return {"message": "SpeakNote Remind API", "version": "1.0.0"}

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify CORS and connectivity"""
    return {
        "message": "API is working",
        "timestamp": datetime.now().isoformat(),
        "cors_enabled": True
    }

@app.get("/debug/otp")
async def debug_otp_endpoint():
    """Debug endpoint to check OTP functionality"""
    try:
        from app.crud import get_user_by_email, set_user_otp
        from app.email import send_otp_email
        import random
        
        return {
            "message": "OTP functions are available",
            "email_config": {
                "username_set": bool(settings.MAIL_USERNAME),
                "password_set": bool(settings.MAIL_PASSWORD),
                "server": settings.MAIL_SERVER
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "message": "OTP functions are NOT available",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/debug/endpoints")
async def debug_endpoints():
    """Debug endpoint to check if all endpoints are available"""
    try:
        from app.crud import get_user_by_email, set_user_otp
        from app.email import send_otp_email
        import random
        
        return {
            "message": "All endpoints are available",
            "endpoints": [
                "/auth/request-login-otp",
                "/auth/login-with-otp", 
                "/auth/request-registration-otp",
                "/auth/register-with-otp"
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "message": "Some endpoints are NOT available",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    from app.crud import create_user, get_user_by_email
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Registration attempt for email: {user_data.email}")
        logger.info(f"Password provided: {bool(user_data.password)}")
        logger.info(f"Full name: {user_data.full_name}")
        
        # Check if user already exists
        existing_user = await get_user_by_email(db, user_data.email)
        if existing_user:
            logger.warning(f"Email already registered: {user_data.email}")
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create user
        logger.info("Creating user...")
        user = await create_user(db, user_data)
        logger.info(f"User registered successfully: {user.id}")
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail="Registration failed. Please try again."
        )

@app.post("/auth/request-login-otp")
async def request_login_otp(email: EmailStr = Form(...), db: AsyncSession = Depends(get_db)):
    """Generate and send an OTP to the user's email."""
    import random
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Processing OTP request for email: {email}")
        
        # Import functions inside try block to catch import errors
        try:
            from app.crud import get_user_by_email, set_user_otp
            from app.email import send_otp_email
        except ImportError as import_error:
            logger.error(f"Import error: {import_error}")
            raise HTTPException(
                status_code=500, 
                detail=f"Server configuration error: {str(import_error)}"
            )
        
        # Check if email configuration is set up
        logger.info(f"Email config - Username: {bool(settings.MAIL_USERNAME)}, Password: {bool(settings.MAIL_PASSWORD)}")
        
        # Get user
        try:
            user = await get_user_by_email(db, email)
            if not user:
                logger.warning(f"User not found for email: {email}")
                raise HTTPException(status_code=404, detail="User not found")
            logger.info(f"User found: {user.id}")
        except Exception as user_error:
            logger.error(f"Error getting user: {user_error}")
            raise HTTPException(
                status_code=500, 
                detail=f"Database error: {str(user_error)}"
            )

        # Generate OTP
        try:
            otp = str(random.randint(100000, 999999))
            logger.info(f"Generated OTP: {otp}")
        except Exception as otp_error:
            logger.error(f"Error generating OTP: {otp_error}")
            raise HTTPException(
                status_code=500, 
                detail=f"OTP generation error: {str(otp_error)}"
            )
        
        # Save OTP to database
        try:
            await set_user_otp(db, user, otp)
            logger.info("OTP saved to database")
        except Exception as db_error:
            logger.error(f"Error saving OTP to database: {db_error}")
            raise HTTPException(
                status_code=500, 
                detail=f"Database save error: {str(db_error)}"
            )
        
        # Check if email configuration is set up
        if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
            logger.warning("Email configuration is missing - returning OTP in response for development")
            return {
                "message": "OTP generated successfully (email not configured)",
                "otp": otp,  # Only include OTP in development
                "development_mode": True
            }
        
        # Send email
        try:
            logger.info("Attempting to send email...")
            await send_otp_email(email, otp)
            logger.info(f"OTP sent successfully to {email}")
            return {"message": "OTP sent successfully"}
        except Exception as email_error:
            logger.error(f"Email sending failed: {str(email_error)}")
            # Clear the OTP since email failed
            try:
                await set_user_otp(db, user, None)
            except:
                pass  # Ignore errors when clearing OTP
            raise HTTPException(
                status_code=500, 
                detail="Failed to send OTP email. Please try again later."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in request_login_otp: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@app.post("/auth/login-with-otp")
async def login_with_otp(
    request: Request,
    email: EmailStr = Form(...),
    otp: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Login user with email and OTP and return access token."""
    from app.crud import verify_user_otp, create_login_history

    user = await verify_user_otp(db, email, otp)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Log login history
    history_data = LoginHistoryCreate(
        user_id=user.id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    await create_login_history(db, history_data)

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/login")
async def login(
    request: Request,
    email: str = Form(...), 
    password: str = Form(...), 
    db: AsyncSession = Depends(get_db)
):
    """Login user and return access token"""
    from app.crud import authenticate_user, create_login_history
    
    user = await authenticate_user(db, email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Log login history
    history_data = LoginHistoryCreate(
        user_id=user.id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    await create_login_history(db, history_data)
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@app.post("/analyze/voice", response_model=dict)
async def analyze_voice(
    audio_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Analyze voice input and extract scheduling information"""
    try:
        # Save audio file temporarily
        file_path = f"uploads/temp_{current_user.id}_{datetime.now().timestamp()}.wav"
        with open(file_path, "wb") as buffer:
            content = await audio_file.read()
            buffer.write(content)
        
        # Analyze voice input
        text_result = await analyze_voice_input(file_path)
        scheduling_info = await extract_scheduling_info(text_result["text"])
        
        # Clean up temporary file
        os.remove(file_path)
        
        return {
            "text": text_result["text"],
            "confidence": text_result["confidence"],
            "scheduling_info": scheduling_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice analysis failed: {str(e)}")

@app.post("/analyze/text", response_model=dict)
async def analyze_text(
    text: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """Analyze text input and extract scheduling information"""
    try:
        analysis_result = await analyze_text_input(text)
        scheduling_info = await extract_scheduling_info(text)
        
        return {
            "analysis": analysis_result,
            "scheduling_info": scheduling_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text analysis failed: {str(e)}")

@app.post("/analyze/image", response_model=dict)
async def analyze_image(
    image_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Analyze image input and extract text and scheduling information"""
    try:
        # Save image file
        file_path = f"uploads/{current_user.id}_{datetime.now().timestamp()}.jpg"
        with open(file_path, "wb") as buffer:
            content = await image_file.read()
            buffer.write(content)
        
        # Analyze image
        image_result = await analyze_image_input(file_path)
        scheduling_info = await extract_scheduling_info(image_result["text"])
        
        return {
            "text": image_result["text"],
            "confidence": image_result["confidence"],
            "image_url": f"/uploads/{os.path.basename(file_path)}",
            "scheduling_info": scheduling_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")

@app.post("/reminders", response_model=ReminderResponse)
async def create_reminder(
    reminder_data: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new reminder"""
    from app.crud import create_reminder as crud_create_reminder
    
    reminder = await crud_create_reminder(db, reminder_data, current_user.id)
    return reminder

@app.get("/reminders", response_model=List[ReminderResponse])
async def get_reminders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all reminders for the current user"""
    from app.crud import get_user_reminders
    
    reminders = await get_user_reminders(db, current_user.id)
    return reminders

@app.get("/reminders/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific reminder by ID"""
    from app.crud import get_reminder_by_id
    
    reminder = await get_reminder_by_id(db, reminder_id, current_user.id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder

@app.put("/reminders/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: int,
    reminder_data: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a reminder"""
    from app.crud import update_reminder as crud_update_reminder
    
    reminder = await crud_update_reminder(db, reminder_id, reminder_data, current_user.id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder

@app.delete("/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a reminder"""
    from app.crud import delete_reminder as crud_delete_reminder
    
    success = await crud_delete_reminder(db, reminder_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"message": "Reminder deleted successfully"}

@app.get("/reminders/upcoming", response_model=List[ReminderResponse])
async def get_upcoming_reminders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get upcoming reminders for the current user"""
    from app.crud import get_upcoming_reminders as crud_get_upcoming_reminders
    
    reminders = await crud_get_upcoming_reminders(db, current_user.id)
    return reminders

@app.post("/reminders/{reminder_id}/complete", response_model=ReminderResponse)
async def complete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a reminder as completed"""
    from app.crud import complete_reminder as crud_complete_reminder
    
    reminder = await crud_complete_reminder(db, reminder_id, current_user.id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder

@app.post("/reminders/{reminder_id}/uncomplete", response_model=ReminderResponse)
async def uncomplete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a reminder as uncompleted"""
    from app.crud import uncomplete_reminder as crud_uncomplete_reminder
    
    reminder = await crud_uncomplete_reminder(db, reminder_id, current_user.id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder

@app.put("/auth/me", response_model=UserResponse)
async def update_current_user(
    full_name: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's profile (e.g., full name)"""
    current_user.full_name = full_name
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user

@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return Response(status_code=200)

@app.options("/test-cors")
async def test_cors():
    """Test endpoint to verify CORS and connectivity"""
    return {
        "message": "API is working",
        "timestamp": datetime.now().isoformat(),
        "cors_enabled": True,
        "allowed_origins": [
            "https://speak-note.vercel.app",
            "http://localhost:3000"
        ]
    }

@app.options("/auth/register", include_in_schema=False)
async def options_auth_register():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "https://speak-note.vercel.app",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Credentials": "true",
        }
    )

@app.post("/auth/request-registration-otp")
async def request_registration_otp(email: EmailStr = Form(...), db: AsyncSession = Depends(get_db)):
    """Generate and send an OTP for new user registration."""
    import random
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Processing registration OTP request for email: {email}")
        
        # Test database connection first
        try:
            logger.info("Testing database connection...")
            result = await db.execute(text("SELECT 1"))
            logger.info("Database connection successful")
        except Exception as db_error:
            logger.error(f"Database connection failed: {db_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Database connection error: {str(db_error)}"
            )
        
        # Import functions inside try block to catch import errors
        try:
            from app.crud import get_user_by_email, set_user_otp
            from app.email import send_otp_email
            logger.info("All imports successful")
        except ImportError as import_error:
            logger.error(f"Import error: {import_error}")
            raise HTTPException(
                status_code=500, 
                detail=f"Server configuration error: {str(import_error)}"
            )
        
        # Check if user already exists
        try:
            logger.info("Checking if user already exists...")
            existing_user = await get_user_by_email(db, email)
            if existing_user:
                logger.warning(f"Email already registered: {email}")
                raise HTTPException(status_code=400, detail="Email already registered. Please use login instead.")
            logger.info("User does not exist, proceeding with registration OTP")
        except Exception as user_check_error:
            logger.error(f"Error checking user existence: {user_check_error}")
            raise HTTPException(
                status_code=500,
                detail=f"User check error: {str(user_check_error)}"
            )
        
        # Generate OTP
        try:
            otp = str(random.randint(100000, 999999))
            logger.info(f"Generated registration OTP: {otp}")
        except Exception as otp_error:
            logger.error(f"Error generating OTP: {otp_error}")
            raise HTTPException(
                status_code=500, 
                detail=f"OTP generation error: {str(otp_error)}"
            )
        
        # Check if email configuration is set up
        logger.info(f"Email config - Username: {bool(settings.MAIL_USERNAME)}, Password: {bool(settings.MAIL_PASSWORD)}")
        if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
            logger.warning("Email configuration is missing - returning OTP in response for development")
            return {
                "message": "Registration OTP generated successfully (email not configured)",
                "otp": otp,  # Only include OTP in development
                "development_mode": True
            }
        
        # Send email
        try:
            logger.info("Attempting to send registration email...")
            await send_otp_email(email, otp)
            logger.info(f"Registration OTP sent successfully to {email}")
            return {"message": "Registration OTP sent successfully"}
        except Exception as email_error:
            logger.error(f"Email sending failed: {str(email_error)}")
            raise HTTPException(
                status_code=500, 
                detail="Failed to send registration OTP email. Please try again later."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in request_registration_otp: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again."
        )

@app.post("/auth/register-with-otp")
async def register_with_otp(
    request: Request,
    email: EmailStr = Form(...),
    otp: str = Form(...),
    full_name: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Register a new user with email and OTP."""
    from app.crud import create_user, get_user_by_email
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Check if user already exists
        existing_user = await get_user_by_email(db, email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # In a real implementation, you'd verify the OTP from temporary storage
        # For now, we'll accept any 6-digit code in development mode
        if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
            # Development mode - accept any 6-digit code
            if not otp.isdigit() or len(otp) != 6:
                raise HTTPException(status_code=400, detail="Invalid OTP format")
        else:
            # Production mode - verify OTP (implement proper verification)
            # For now, we'll accept any 6-digit code
            if not otp.isdigit() or len(otp) != 6:
                raise HTTPException(status_code=400, detail="Invalid OTP")
        
        # Create user without password
        user_data = UserCreate(
            email=email,
            password="",  # No password for OTP users
            full_name=full_name
        )
        
        user = await create_user(db, user_data)
        
        # Log registration
        logger.info(f"New user registered with OTP: {user.id}")
        
        # Auto-login after registration
        from app.auth import create_access_token
        access_token = create_access_token(data={"sub": user.email})
        
        return {
            "message": "Registration successful",
            "access_token": access_token,
            "token_type": "bearer",
            "user": user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration with OTP failed: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Registration failed. Please try again."
        )

@app.get("/test-registration-otp")
async def test_registration_otp():
    """Test endpoint to simulate registration OTP functionality"""
    try:
        import random
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Test email import
        from app.email import send_otp_email
        
        # Test CRUD import
        from app.crud import get_user_by_email, set_user_otp
        
        # Generate test OTP
        otp = str(random.randint(100000, 999999))
        
        return {
            "message": "Registration OTP test successful",
            "test_otp": otp,
            "email_config": {
                "username_set": bool(settings.MAIL_USERNAME),
                "password_set": bool(settings.MAIL_PASSWORD),
                "server": settings.MAIL_SERVER
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        import traceback
        return {
            "message": "Registration OTP test failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/test-register-cors")
async def test_register_cors():
    """Test endpoint to verify CORS specifically for register endpoint"""
    return {
        "message": "Register CORS test successful",
        "timestamp": datetime.now().isoformat(),
        "method": "POST",
        "endpoint": "/auth/register"
    }

@app.get("/test-database")
async def test_database(db: AsyncSession = Depends(get_db)):
    """Test endpoint to verify database connectivity and basic operations"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Testing database connectivity...")
        
        # Test basic database operations
        from app.crud import get_user_by_email
        
        # Try to query the database
        result = await db.execute("SELECT 1")
        logger.info("Database query successful")
        
        # Test user table
        try:
            from app.models import User
            result = await db.execute("SELECT COUNT(*) FROM users")
            count = result.scalar()
            logger.info(f"User table accessible, count: {count}")
        except Exception as table_error:
            logger.error(f"User table error: {table_error}")
            return {
                "message": "Database connected but user table has issues",
                "error": str(table_error),
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "message": "Database test successful",
            "user_count": count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Database test failed: {str(e)}")
        return {
            "message": "Database test failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/run-migration")
async def run_migration_endpoint(db: AsyncSession = Depends(get_db)):
    """Run database migration to fix hashed_password field"""
    import logging
    logger = logging.getLogger(__name__)
    
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
        table_structure = []
        for column in columns:
            table_structure.append({
                "column": column[0],
                "type": column[2],
                "nullable": column[1]
            })
        
        return {
            "message": "Migration completed successfully!",
            "table_structure": table_structure,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {str(e)}"
        )

@app.get("/test-crud")
async def test_crud_operations(db: AsyncSession = Depends(get_db)):
    """Test endpoint to verify CRUD operations"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Testing CRUD operations...")
        
        # Test imports
        try:
            from app.crud import get_user_by_email, create_user
            from app.schemas import UserCreate
            logger.info("CRUD imports successful")
        except Exception as import_error:
            logger.error(f"CRUD import error: {import_error}")
            return {
                "message": "CRUD import failed",
                "error": str(import_error),
                "timestamp": datetime.now().isoformat()
            }
        
        # Test database query
        try:
            result = await db.execute(text("SELECT COUNT(*) FROM users"))
            count = result.scalar()
            logger.info(f"User count query successful: {count}")
        except Exception as query_error:
            logger.error(f"Database query error: {query_error}")
            return {
                "message": "Database query failed",
                "error": str(query_error),
                "timestamp": datetime.now().isoformat()
            }
        
        # Test get_user_by_email with non-existent email
        try:
            test_email = "test@example.com"
            user = await get_user_by_email(db, test_email)
            logger.info(f"get_user_by_email test successful, user: {user}")
        except Exception as crud_error:
            logger.error(f"get_user_by_email error: {crud_error}")
            return {
                "message": "get_user_by_email failed",
                "error": str(crud_error),
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "message": "CRUD operations test successful",
            "user_count": count,
            "get_user_test": "passed",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"CRUD test failed: {str(e)}")
        return {
            "message": "CRUD test failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/test-user-model")
async def test_user_model(db: AsyncSession = Depends(get_db)):
    """Test endpoint to verify User model and database session"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Testing User model...")
        
        # Test User model import
        try:
            from app.models import User
            logger.info("User model import successful")
        except Exception as model_error:
            logger.error(f"User model import error: {model_error}")
            return {
                "message": "User model import failed",
                "error": str(model_error),
                "timestamp": datetime.now().isoformat()
            }
        
        # Test database session with User model
        try:
            result = await db.execute(text("SELECT * FROM users LIMIT 1"))
            user_data = result.fetchone()
            logger.info(f"User table query successful, found: {bool(user_data)}")
        except Exception as session_error:
            logger.error(f"Database session error: {session_error}")
            return {
                "message": "Database session failed",
                "error": str(session_error),
                "timestamp": datetime.now().isoformat()
            }
        
        # Test table structure
        try:
            result = await db.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            table_structure = []
            for col in columns:
                table_structure.append({
                    "name": col[0],
                    "type": col[1],
                    "nullable": col[2]
                })
            logger.info(f"Table structure retrieved: {len(table_structure)} columns")
        except Exception as structure_error:
            logger.error(f"Table structure error: {structure_error}")
            return {
                "message": "Table structure check failed",
                "error": str(structure_error),
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "message": "User model test successful",
            "user_found": bool(user_data),
            "table_structure": table_structure,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"User model test failed: {str(e)}")
        return {
            "message": "User model test failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    ) 