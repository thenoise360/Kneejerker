from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import current_config

app = Flask(__name__)

# Use the current configuration
config = current_config

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+mysqldb://{config.USER}:{config.PASSWORD}@{config.HOST}/{config.DATABASE}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS

db = SQLAlchemy(app)

# Ensure the database connection is initialized within an application context
with app.app_context():
    db.create_all()

# Import the views to register routes
import FPL_site.views
