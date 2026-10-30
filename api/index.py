import sys
from pathlib import Path

# Add parent directory to path so we can import road_roughness_app
sys.path.insert(0, str(Path(__file__).parent.parent))

from road_roughness_app import app

# Vercel serverless function handler
handler = app
