import sys
import os
from pathlib import Path

# Add parent directory to path so we can import road_roughness_app
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set base directory for imports
os.chdir(Path(__file__).parent.parent)

from road_roughness_app import app

# Vercel requires this exact name
app = app
