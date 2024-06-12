from flask import Flask
import os

template_dir = os.path.abspath('FPL_site/templates')
app = Flask(__name__, template_folder=template_dir)

from FPL_site import views
