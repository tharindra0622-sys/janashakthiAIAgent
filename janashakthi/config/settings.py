import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'janashakthi-secret-key-2025')
    DEBUG = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'janashakthi.db')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    GEMINI_MODEL   = 'gemini-2.5-flash'

    # ── Groq API (used for Jana chatbot + document verification) ────────────
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
    GROQ_MODEL   = 'llama-3.3-70b-versatile'

    # ── Email / OTP config ──────────────────────────────────────────
    MAIL_SERVER   = 'smtp.gmail.com'
    MAIL_PORT     = 587
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')   # your Gmail address
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')   # Gmail App Password
    OTP_EXPIRY_SECONDS = 300                              # 5 minutes

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
