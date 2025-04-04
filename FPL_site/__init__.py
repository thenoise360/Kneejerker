from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import current_config
import cryptography
import os
import mimetypes
from whitenoise import WhiteNoise

# ✅ Ensure correct MIME type for JS modules
mimetypes.add_type('application/javascript', '.js')

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')

# Secret key for sessions
app.secret_key = os.urandom(24)

# Use environment-specific config
config = current_config
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{config.USER}:{config.PASSWORD}@{config.HOST}/{config.DATABASE}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS

db = SQLAlchemy(app)

# Create tables if needed
with app.app_context():
    db.create_all()

# Register routes
import FPL_site.views
