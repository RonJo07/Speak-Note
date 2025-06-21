from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from typing import List
from app.config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_otp_email(email: EmailStr, otp: str):
    """
    Sends an email with the One-Time Password.
    """
    html = f"""
    <div style="font-family: Arial, sans-serif; text-align: center; color: #333;">
        <h2>SpeakNote Remind - Your Login Code</h2>
        <p>Here is your one-time password to log in:</p>
        <p style="font-size: 24px; font-weight: bold; letter-spacing: 2px; color: #5e35b1;">{otp}</p>
        <p>This code will expire in 10 minutes.</p>
        <p style="font-size: 12px; color: #888;">If you did not request this, please ignore this email.</p>
    </div>
    """

    message = MessageSchema(
        subject="Your SpeakNote Remind Login Code",
        recipients=[email],
        body=html,
        subtype="html"
    )

    fm = FastMail(conf)
    await fm.send_message(message) 