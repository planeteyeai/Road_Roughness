import sys
import os
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Change to parent directory so relative paths work
try:
    os.chdir(parent_dir)
except:
    pass

# Import the FastAPI app
try:
    from road_roughness_app import app
except Exception as e:
    print(f"Error importing app: {e}")
    import traceback
    traceback.print_exc()
    raise

# Export for Vercel
# Vercel looks for 'app' or 'application' variable
app = app
