"""Browser-based login and logout endpoints for the dashboard."""

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
    """Validate and sanitize a redirect target path.

    Prevents open redirect vulnerabilities by ensuring the path is relative
    and does not contain scheme or netloc components.

    Args:
        next_path: The proposed redirect target from the query string.

    Returns:
        The safe redirect path, or "/dashboard" if the input is invalid.
    """
    if not next_path or not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path:
        return "/dashboard"

    parsed = urlsplit(next_path)
    if parsed.scheme or parsed.netloc:
        return "/dashboard"

    return next_path


def _render_login(request: Request, next_path: str, error: str | None = None, status_code: int = 200):
    """Render the login page template with the given context.

    Args:
        request: The incoming HTTP request (required for template rendering).
        next_path: Where to redirect after successful login.
        error: Optional error message to display on the login page.
        status_code: HTTP status code for the response (default 200).

    Returns:
        An HTML response rendering the login.html template.
    """
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
    """Display the dashboard login page.

    If the user already has a valid Bearer token in headers or an active
    session, they are redirected directly to the dashboard instead.

    Args:
        request: The incoming HTTP request.
        next: Optional query parameter specifying where to redirect after login.

    Returns:
        HTML login page, or a 303 redirect if already authenticated or
        analytics routes are disabled.
    """
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
    """Handle login form submission.

    Validates the submitted token and, if correct, creates an active
    dashboard session cookie before redirecting to the target page.

    Args:
        request: The incoming HTTP request containing the form data.

    Returns:
        A 303 redirect to the target page on success, or the login page
        with an error message on failure.
    """
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
    """Clear the dashboard session and redirect to the login page.

    Args:
        request: The incoming HTTP request.

    Returns:
        A 303 redirect to /login after clearing the session.
    """
    if not settings.enable_analytics_routes:
        raise HTTPException(status_code=404, detail="Analytics routes disabled")

    auth.clear_dashboard_session(request)
    return RedirectResponse(url="/login", status_code=303)
