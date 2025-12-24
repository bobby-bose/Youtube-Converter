import os
import sys

# Add the project directory to the Python path
project_home = '/home/YoutubeConverter/Youtube-Converter'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Import the Flask app
from app import app

# PythonAnywhere specific configuration
app.config['UPLOAD_FOLDER'] = os.path.expanduser('~/downloads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Expose the application variable
application = app
