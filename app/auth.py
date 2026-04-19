"""Bearer token and session-based authentication for the Health Connect webhook service."""

from secrets import compare_digest

from fastapi import HTTPException, Request


class BearerAuth:
    """Handles Bearer token verification and dashboard session authentication.

    Supports two authentication modes:
    - Bearer token via Authorization header
    - Session-based authentication for browser dashboard access
    """

    dashboard_session_key = "dashboard_authenticated"

    def __init__(self, token: str):
        """Initialize with the expected Bearer token.

        Args:
            token: The secret token that valid Bearer clients must present.
        """
        self.token = token

    def verify_token(self, token: str | None) -> bool:
        """Verify that the provided token matches the configured token.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            token: The token string to verify, or None.

        Returns:
            True if the token is valid.

        Raises:
            HTTPException: If the token is missing or does not match.
        """
        if token is None or token == "":
            raise HTTPException(status_code=401, detail="Missing token")
        if not compare_digest(token, self.token):
            raise HTTPException(status_code=401, detail="Invalid token")
        return True

    def _extract_bearer_token(self, authorization: str | None) -> str:
        """Extract the token value from a Bearer authorization header.

        Args:
            authorization: The full Authorization header value (e.g., "Bearer xyz").

        Returns:
            The extracted token string.

        Raises:
            HTTPException: If the header is missing or malformed.
        """
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing authorization header")
        parts = authorization.split(" ", 1)
        if len(parts) != 2 or parts[0] != "Bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        return parts[1]

    def verify(self, authorization: str | None) -> bool:
        """Verify a raw Authorization header as a Bearer token.

        Args:
            authorization: The full Authorization header value.

        Returns:
            True if the Bearer token is valid.

        Raises:
            HTTPException: If verification fails.
        """
        return self.verify_token(self._extract_bearer_token(authorization))

    def require_bearer_request(self, request: Request) -> bool:
        """Verify the request has a valid Bearer token in its Authorization header.

        Args:
            request: The incoming FastAPI request.

        Returns:
            True if the request contains a valid Bearer token.

        Raises:
            HTTPException: If the token is missing or invalid.
        """
        return self.verify(request.headers.get("authorization"))

    def has_valid_bearer_request(self, request: Request) -> bool:
        """Check whether the request has a valid Bearer token without raising on failure.

        Args:
            request: The incoming FastAPI request.

        Returns:
            True if the request has a valid Bearer token, False otherwise.
        """
        authorization = request.headers.get("authorization")
        if not authorization:
            return False
        self.verify(authorization)
        return True

    def start_dashboard_session(self, request: Request) -> None:
        """Start a new dashboard session for the given request.

        Clears any existing session data and marks the session as authenticated.

        Args:
            request: The incoming FastAPI request with an active session middleware.
        """
        request.session.clear()
        request.session[self.dashboard_session_key] = True

    def clear_dashboard_session(self, request: Request) -> None:
        """Clear the dashboard session for the given request.

        Silently handles the case where no session is available.

        Args:
            request: The incoming FastAPI request with an active session middleware.
        """
        try:
            request.session.clear()
        except AssertionError:
            return

    def has_dashboard_session(self, request: Request) -> bool:
        """Check whether the request has an active dashboard session.

        Args:
            request: The incoming FastAPI request with an active session middleware.

        Returns:
            True if the session exists and is marked as authenticated.
        """
        try:
            session = request.session
        except AssertionError:
            return False
        return bool(session.get(self.dashboard_session_key))

    def require_dashboard_access(
        self, request: Request, *, persist_bearer_session: bool = False
    ) -> bool:
        """Require that the request has valid authentication for dashboard access.

        Accepts either a valid Bearer token or an active dashboard session.

        Args:
            request: The incoming FastAPI request.
            persist_bearer_session: If True and a Bearer token is present, persist it as
                a session so subsequent requests can use session auth.

        Returns:
            True if the request is authenticated.

        Raises:
            HTTPException: If neither Bearer token nor session auth is valid.
        """
        if self.has_valid_bearer_request(request):
            if persist_bearer_session:
                self.start_dashboard_session(request)
            return True

        if self.has_dashboard_session(request):
            return True

        raise HTTPException(status_code=401, detail="Missing authorization header or dashboard session")
