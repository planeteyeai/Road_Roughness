"""Vercel serverless handler for FastAPI app"""
import sys
import os
import json
from pathlib import Path

# Debug: Print environment info
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"__file__: {__file__}")

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print(f"Added to path: {parent_dir}")

# Change to parent directory so relative paths work
try:
    os.chdir(parent_dir)
    print(f"Changed directory to: {parent_dir}")
except Exception as e:
    print(f"Could not change directory: {e}")

# List files to debug
print(f"Files in parent dir: {list(Path(parent_dir).iterdir())[:10]}")
if (Path(parent_dir) / 'static').exists():
    print(f"Static dir exists!")
else:
    print(f"Static dir NOT found!")

# Import the FastAPI app
import_error = None
try:
    print("Attempting to import road_roughness_app...")
    from road_roughness_app import app
    print("Successfully imported app!")
except Exception as exc:
    import_error = exc
    print(f"ERROR importing app: {exc}")
    import traceback
    traceback.print_exc()
    
    # Create a dummy app that shows the error
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI()
    
    @app.get("/")
    def error_page():
        return JSONResponse({
            "error": "Failed to import main app",
            "message": str(import_error),
            "traceback": traceback.format_exc(),
            "help": "Check function logs in Vercel dashboard"
        }, status_code=500)
    
    @app.get("/api/config")
    def error_config():
        return JSONResponse({
            "error": "App failed to start",
            "message": str(import_error)
        }, status_code=500)

# Export for Vercel
app = app
