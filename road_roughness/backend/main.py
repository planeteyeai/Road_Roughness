"""Start the backend:  python main.py   (settings in .env)"""
import uvicorn

from app.api import app
from app.config import APP_VERSION, HOST, PORT, SERVE_FRONTEND, FRONTEND_DIR

if __name__ == "__main__":
    print(f"\n  Road Roughness Platform backend {APP_VERSION}"
          f"\n  API:      http://{HOST}:{PORT}/api/config"
          f"\n  API docs: http://{HOST}:{PORT}/docs", flush=True)
    if SERVE_FRONTEND and FRONTEND_DIR.is_dir():
        print(f"  Web page: http://{HOST}:{PORT}/   (frontend folder served too)", flush=True)
    print(flush=True)
    uvicorn.run(app, host=HOST, port=PORT)
