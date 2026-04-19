from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import BearerAuth
from app.config import Settings

settings = Settings()
auth = BearerAuth(token=settings.ingest_token)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

router = APIRouter(tags=["browser-auth"])


def _safe_next_path(next_path: str | None) -> str:
    if not next_path or not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path:
        return "/dashboard"

    parsed = urlsplit(next_path)
    if parsed.scheme or parsed.netloc:
        return "/dashboard"

    return next_path


def _render_login(request: Request, next_path: str, error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "title": "Dashboard Login",
            "next_path": next_path,
            "error": error,
        },
        status_code=status_code,
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str | None = Query(default=None)):
    if not settings.enable_analytics_routes:
        raise HTTPException(status_code=404, detail="Analytics routes disabled")

    next_path = _safe_next_path(next)

    try:
        if auth.has_valid_bearer_request(request):
            auth.start_dashboard_session(request)
            return RedirectResponse(url=next_path, status_code=303)
    except HTTPException:
        pass

    if auth.has_dashboard_session(request):
        return RedirectResponse(url=next_path, status_code=303)

    return _render_login(request, next_path)


@router.post("/login")
async def login_submit(request: Request):
    if not settings.enable_analytics_routes:
        raise HTTPException(status_code=404, detail="Analytics routes disabled")

    body = (await request.body()).decode("utf-8")
    form_data = parse_qs(body)
    next_path = _safe_next_path((form_data.get("next") or [None])[0])
    token = (form_data.get("token") or [None])[0]

    try:
        auth.verify_token(token)
    except HTTPException as exc:
        return _render_login(request, next_path, error=exc.detail, status_code=exc.status_code)

    auth.start_dashboard_session(request)
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/logout")
async def logout(request: Request):
    if not settings.enable_analytics_routes:
        raise HTTPException(status_code=404, detail="Analytics routes disabled")

    auth.clear_dashboard_session(request)
    return RedirectResponse(url="/login", status_code=303)