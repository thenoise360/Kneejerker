import sys
import os

# Ensure the FPL_site directory is in the sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
if os.path.join(project_root, 'FPL_site') not in sys.path:
    sys.path.append(os.path.join(project_root, 'FPL_site'))

from sqlFunction import update_all_tables

update_all_tables()