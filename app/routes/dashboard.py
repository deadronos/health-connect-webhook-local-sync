from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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

    try:
        auth.require_dashboard_access(request, persist_bearer_session=True)
    except HTTPException:
        if request.headers.get("authorization"):
            raise
        return RedirectResponse(url="/login?next=%2Fdashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "title": "Health Analytics Dashboard",
        },
    )
