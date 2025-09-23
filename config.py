"""Configuration settings for the webhook."""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    
    # Webhook specific settings
    WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request size