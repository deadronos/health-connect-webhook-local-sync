from fastapi import HTTPException


class BearerAuth:
    def __init__(self, token: str):
        self.token = token

    def verify(self, authorization: str | None) -> bool:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing authorization header")
        parts = authorization.split(" ")
        if len(parts) != 2 or parts[0] != "Bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        if parts[1] != self.token:
            raise HTTPException(status_code=401, detail="Invalid token")
        return True