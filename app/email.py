from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from typing import List
from app.config import settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_email_config():
    """Get email configuration based on environment variables"""
    # Check if using SendGrid
    if settings.MAIL_SERVER == "smtp.sendgrid.net":
        return ConnectionConfig(
            MAIL_USERNAME="apikey",  # SendGrid uses 'apikey' as username
            MAIL_PASSWORD=settings.MAIL_PASSWORD,  # This should be your SendGrid API key
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=587,
            MAIL_SERVER="smtp.sendgrid.net",
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True
        )
    else:
        # Default Gmail configuration
        return ConnectionConfig(
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

conf = get_email_config()

async def send_otp_email(email: EmailStr, otp: str):
    """
    Sends an email with the One-Time Password.
    """
    try:
        html = f"""
        <div style="font-family: Arial, sans-serif; text-align: center; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0; font-size: 28px;">SpeakNote Remind</h1>
            </div>
            <div style="background: #f8f9fa; padding: 30px; border-radius: 10px;">
                <h2 style="color: #333; margin-bottom: 20px;">Your Login Code</h2>
                <p style="color: #666; margin-bottom: 20px;">Here is your one-time password to log in:</p>
                <div style="background: #5e35b1; color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p style="font-size: 32px; font-weight: bold; letter-spacing: 4px; margin: 0;">{otp}</p>
                </div>
                <p style="color: #666; font-size: 14px;">This code will expire in 10 minutes.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #888; font-size: 12px;">If you did not request this login code, please ignore this email.</p>
            </div>
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
        logger.info(f"OTP email sent successfully to {email}")
        
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        raise Exception(f"Email sending failed: {str(e)}") 