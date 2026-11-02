"""Project folders on disk: lookup, NDWI image sets, zips, clean-up."""

import io
import re
import shutil
import zipfile
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .config import PROJECTS_DIR
from .tasks import TASKS
from .utils import read_json


_PID_RE = re.compile(r"^[a-f0-9]{10}$")


_RUN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_to_\d{4}-\d{2}-\d{2}_cc\d{1,3}$")


def project_dir(pid: str) -> Path:
    if not _PID_RE.match(pid or ""):
        raise HTTPException(404, "Unknown project.")
    d = PROJECTS_DIR / pid
    if not (d / "project.json").exists():
        raise HTTPException(404, "Unknown project.")
    return d


def list_runs(pid, pdir):
    out = []
    ndwi_root = pdir / "ndwi"
    if not ndwi_root.is_dir():
        return out
    for d in sorted(ndwi_root.iterdir()):
        f = d / "run.json"
        if not f.exists():
            continue
        run = read_json(f)
        if run.get("status") == "running":
            t = TASKS.get(run.get("task", ""))
            if not t or t["status"] not in ("queued", "running"):
                run["status"] = "interrupted"
        run["zip_url"] = f"/api/projects/{pid}/ndwi/{run['id']}/zip"
        out.append(run)
    return out


def zip_folder_response(folder: Path, arc_root: str, filename: str, only=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and (only is None or path.parent.name in only):
                zf.write(path, f"{arc_root}/{path.relative_to(folder).as_posix()}")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def delete_other_projects(keep_pid: str):
    """Only the newest project is kept. project.json goes first so a folder that
    can't be fully removed (a report open in Excel, say) is no longer listed."""
    for d in PROJECTS_DIR.iterdir():
        if d.is_dir() and d.name != keep_pid:
            try:
                (d / "project.json").unlink(missing_ok=True)
            except OSError:
                pass
            shutil.rmtree(d, ignore_errors=True)
            print(f"   deleted previous project {d.name}", flush=True)
