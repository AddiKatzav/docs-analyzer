from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

from app.api.analyze import router as analyze_router
from app.api.config import router as config_router
from app.api.rules import router as rules_router
from app.api.runs import router as runs_router
from app.services.paths import FRONTEND_DIR, ensure_data_dirs

ensure_data_dirs()

app = FastAPI(title="Global Rules DOCX Analyzer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(config_router, prefix="/api")
app.include_router(rules_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
app.include_router(runs_router, prefix="/api")

_frontend_root = FRONTEND_DIR.resolve()
_index_file = _frontend_root / "index.html"
_frontend_available = _frontend_root.exists() and _index_file.exists()
_frontend_no_cache_headers = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

@app.get("/", include_in_schema=False, response_model=None)
def serve_frontend_root():
    if _frontend_available:
        return FileResponse(_index_file, headers=_frontend_no_cache_headers)
    # In Docker split mode, UI is served by the frontend container on port 3000.
    return JSONResponse(
        {
            "detail": "UI is available on http://localhost:3000 in Docker mode. API health: /api/health"
        }
    )


# Localhost fallback: serve full UI assets directly from FastAPI when frontend files exist.
if _frontend_available:
    @app.get("/{file_path:path}", include_in_schema=False)
    def serve_frontend_files(file_path: str) -> FileResponse:
        if file_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        requested = (_frontend_root / file_path).resolve()
        if not str(requested).startswith(str(_frontend_root)):
            raise HTTPException(status_code=404, detail="Not Found")
        if requested.is_file():
            return FileResponse(requested, headers=_frontend_no_cache_headers)
        if _index_file.exists():
            return FileResponse(_index_file, headers=_frontend_no_cache_headers)
        raise HTTPException(status_code=404, detail="Frontend file not found.")
