import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the environment variables
host = os.getenv('HOST')
user = os.getenv('USER')
password = os.getenv('PASSWORD')

# Debugging output to verify environment variables are loaded
print(f"Host: {host}, User: {user}, Password: {password}")
