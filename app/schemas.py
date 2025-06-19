from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Reminder schemas
class ReminderBase(BaseModel):
    title: str
    description: Optional[str] = None
    scheduled_for: datetime
    is_important: bool = False
    timezone: Optional[str] = None  # User's timezone (IANA string)

class ReminderCreate(ReminderBase):
    original_text: Optional[str] = None
    confidence_score: Optional[float] = None
    source_type: Optional[str] = None
    image_url: Optional[str] = None

class ReminderResponse(ReminderBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_completed: bool
    original_text: Optional[str] = None
    confidence_score: Optional[float] = None
    source_type: Optional[str] = None
    image_url: Optional[str] = None
    
    class Config:
        from_attributes = True

# AI Analysis schemas
class SchedulingInfo(BaseModel):
    detected_date: Optional[datetime] = None
    detected_time: Optional[str] = None
    confidence: float
    extracted_text: str
    suggested_title: Optional[str] = None

class VoiceAnalysisResult(BaseModel):
    text: str
    confidence: float
    scheduling_info: SchedulingInfo

class TextAnalysisResult(BaseModel):
    analysis: dict
    scheduling_info: SchedulingInfo

class ImageAnalysisResult(BaseModel):
    text: str
    confidence: float
    image_url: str
    scheduling_info: SchedulingInfo 