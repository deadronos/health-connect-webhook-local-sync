from secrets import compare_digest

from fastapi import HTTPException, Request


class BearerAuth:
    dashboard_session_key = "dashboard_authenticated"

    def __init__(self, token: str):
        self.token = token

    def verify_token(self, token: str | None) -> bool:
        if token is None or token == "":
            raise HTTPException(status_code=401, detail="Missing token")
        if not compare_digest(token, self.token):
            raise HTTPException(status_code=401, detail="Invalid token")
        return True

    def _extract_bearer_token(self, authorization: str | None) -> str:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing authorization header")
        parts = authorization.split(" ", 1)
        if len(parts) != 2 or parts[0] != "Bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        return parts[1]

    def verify(self, authorization: str | None) -> bool:
        return self.verify_token(self._extract_bearer_token(authorization))

    def require_bearer_request(self, request: Request) -> bool:
        return self.verify(request.headers.get("authorization"))

    def has_valid_bearer_request(self, request: Request) -> bool:
        authorization = request.headers.get("authorization")
        if not authorization:
            return False
        self.verify(authorization)
        return True

    def start_dashboard_session(self, request: Request) -> None:
        request.session.clear()
        request.session[self.dashboard_session_key] = True

    def clear_dashboard_session(self, request: Request) -> None:
        try:
            request.session.clear()
        except AssertionError:
            return

    def has_dashboard_session(self, request: Request) -> bool:
        try:
            session = request.session
        except AssertionError:
            return False
        return bool(session.get(self.dashboard_session_key))

    def require_dashboard_access(self, request: Request, *, persist_bearer_session: bool = False) -> bool:
        if self.has_valid_bearer_request(request):
            if persist_bearer_session:
                self.start_dashboard_session(request)
            return True

        if self.has_dashboard_session(request):
            return True

        raise HTTPException(status_code=401, detail="Missing authorization header or dashboard session")