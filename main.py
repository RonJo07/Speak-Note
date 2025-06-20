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

from app.database import engine, get_db, create_tables
from app.models import Base, Reminder, User
from app.schemas import ReminderCreate, ReminderResponse, UserCreate, UserResponse
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
        "https://speak-now-live.vercel.app",  # <-- Updated to your actual Vercel domain
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate, db=Depends(get_db)):
    """Register a new user"""
    from app.crud import create_user, get_user_by_email
    
    # Check if user already exists
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = await create_user(db, user_data)
    return user

@app.post("/auth/login")
async def login(email: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    """Login user and return access token"""
    from app.crud import authenticate_user
    
    user = await authenticate_user(db, email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
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
    db=Depends(get_db)
):
    """Create a new reminder"""
    from app.crud import create_reminder
    
    reminder = await create_reminder(db, reminder_data, current_user.id)
    return reminder

@app.get("/reminders", response_model=List[ReminderResponse])
async def get_reminders(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get all reminders for the current user"""
    from app.crud import get_user_reminders
    
    reminders = await get_user_reminders(db, current_user.id)
    return reminders

@app.get("/reminders/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get a specific reminder"""
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
    db=Depends(get_db)
):
    """Update a reminder"""
    from app.crud import update_reminder_by_id
    
    reminder = await update_reminder_by_id(db, reminder_id, reminder_data, current_user.id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder

@app.delete("/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Delete a reminder"""
    from app.crud import delete_reminder_by_id
    
    success = await delete_reminder_by_id(db, reminder_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"message": "Reminder deleted successfully"}

@app.get("/reminders/upcoming", response_model=List[ReminderResponse])
async def get_upcoming_reminders(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get upcoming reminders for the current user"""
    from app.crud import get_upcoming_reminders
    
    reminders = await get_upcoming_reminders(db, current_user.id)
    return reminders

@app.post("/reminders/{reminder_id}/complete", response_model=ReminderResponse)
async def complete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Mark a reminder as completed"""
    from app.crud import mark_reminder_completed
    
    reminder = await mark_reminder_completed(db, reminder_id, current_user.id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder

@app.put("/auth/me", response_model=UserResponse)
async def update_current_user(
    full_name: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
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

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    ) 