from flask import Flask, request
import os
import logging

template_dir = os.path.abspath('FPL_site/templates')
static_dir = os.path.abspath('FPL_site/static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.before_request
def log_request_info():
    logger.info(f"Request: {request.method} {request.path}")

from FPL_site import views
