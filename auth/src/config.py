import os
from datetime import timedelta

class Config:
    """Authentication service configuration"""

    # Flask settings
    SECRET_KEY = os.getenv('AUTH_SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database settings
    POSTGRES_USER = os.getenv('POSTGRES_USER_FILE')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD_FILE')

    # Read credentials from Docker secrets
    if POSTGRES_USER and os.path.exists(POSTGRES_USER):
        with open(POSTGRES_USER, 'r') as f:
            POSTGRES_USER = f.read().strip()
    else:
        POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')

    if POSTGRES_PASSWORD and os.path.exists(POSTGRES_PASSWORD):
        with open(POSTGRES_PASSWORD, 'r') as f:
            POSTGRES_PASSWORD = f.read().strip()
    else:
        POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')

    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'postgres')
    POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'asset_management')

    SQLALCHEMY_DATABASE_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }

    # JWT settings
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv('JWT_ACCESS_TOKEN_HOURS', '1')))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_DAYS', '30')))
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'

    # Redis settings
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_PASSWORD_FILE = os.getenv('REDIS_PASSWORD_FILE')

    if REDIS_PASSWORD_FILE and os.path.exists(REDIS_PASSWORD_FILE):
        with open(REDIS_PASSWORD_FILE, 'r') as f:
            REDIS_PASSWORD = f.read().strip()
    else:
        REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

    # Active Directory settings
    AD_ENABLED = os.getenv('AD_ENABLED', 'false').lower() == 'true'
    AD_SERVER = os.getenv('AD_SERVER', '')
    AD_PORT = int(os.getenv('AD_PORT', '389'))
    AD_USE_SSL = os.getenv('AD_USE_SSL', 'false').lower() == 'true'
    AD_BASE_DN = os.getenv('AD_BASE_DN', '')
    AD_USER_DN = os.getenv('AD_USER_DN', '')
    AD_BIND_USER = os.getenv('AD_BIND_USER', '')
    AD_BIND_PASSWORD = os.getenv('AD_BIND_PASSWORD', '')
    AD_USER_SEARCH_FILTER = os.getenv('AD_USER_SEARCH_FILTER', '(sAMAccountName={username})')
    AD_GROUP_SEARCH_FILTER = os.getenv('AD_GROUP_SEARCH_FILTER', '(member={user_dn})')

    # Authentication settings
    MAX_FAILED_LOGIN_ATTEMPTS = int(os.getenv('MAX_FAILED_LOGIN_ATTEMPTS', '5'))
    ACCOUNT_LOCKOUT_MINUTES = int(os.getenv('ACCOUNT_LOCKOUT_MINUTES', '15'))

    # CORS settings
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
