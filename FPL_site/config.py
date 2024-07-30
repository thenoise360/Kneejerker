import os
from dotenv import load_dotenv

class Config:
    """Base configuration."""
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Development configuration."""
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
    HOST = os.getenv('HOST')
    USER = os.getenv('USER')
    PASSWORD = os.getenv('PASSWORD')
    DATABASE = os.getenv('DATABASE')

    # Print out the variables for debugging
    print(f"Development - HOST: {HOST}")
    print(f"Development - USER: {USER}")
    print(f"Development - PASSWORD: {PASSWORD}")
    print(f"Development - DATABASE: {DATABASE}")

class ProductionConfig(Config):
    """Production configuration."""
    HOST = os.getenv('HOST')
    USER = os.getenv('USER')
    PASSWORD = os.getenv('PASSWORD')
    DATABASE = os.getenv('DATABASE')

def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig()
    else:
        return DevelopmentConfig()

current_config = get_config()
