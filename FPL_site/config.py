import os
from dotenv import load_dotenv

class Config:
    """Base configuration."""
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Hides the player momentum card until the daily job has data. Off by default.
    FEATURE_MOMENTUM = False

class DevelopmentConfig(Config):
    """Development configuration."""
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
    HOST = os.getenv('HOST')
    USER = os.getenv('USER')
    PASSWORD = os.getenv('PASSWORD')
    DATABASE = os.getenv('DATABASE')
    MIXPANEL_TOKEN = os.getenv('MIXPANEL_TOKEN')
    FEATURE_MOMENTUM = os.getenv('FEATURE_MOMENTUM', '').lower() == 'true'

    # Print out the variables for debugging
    print(f"Development - HOST: {HOST}")
    print(f"Development - USER: {USER}")
    print(f"Development - DATABASE: {DATABASE}")

class ProductionConfig(Config):
    """Production configuration."""
    HOST = os.getenv('HOST')
    USER = os.getenv('USER')
    PASSWORD = os.getenv('PASSWORD')
    DATABASE = os.getenv('DATABASE')
    MIXPANEL_TOKEN = os.getenv('MIXPANEL_TOKEN')
    FEATURE_MOMENTUM = os.getenv('FEATURE_MOMENTUM', '').lower() == 'true'

    print(f"Production - MIXPANEL_TOKEN: {MIXPANEL_TOKEN}")

def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig()
    else:
        return DevelopmentConfig()

current_config = get_config()
