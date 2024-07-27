from flask import Flask, render_template
import os

template_dir = os.path.abspath('FPL_site/templates')
static_dir = os.path.abspath('FPL_site/static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

from FPL_site import views
