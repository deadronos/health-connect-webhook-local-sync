from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth import BearerAuth
from app.config import Settings

settings = Settings()
auth = BearerAuth(token=settings.ingest_token)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not settings.enable_analytics_routes:
        raise HTTPException(status_code=404, detail="Analytics routes disabled")

    auth_header = request.headers.get("authorization")
    auth.verify(auth_header)
    bearer_token = auth_header.split(" ", 1)[1]

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "title": "Health Analytics Dashboard",
            "bearer_token": bearer_token,
        },
    )
