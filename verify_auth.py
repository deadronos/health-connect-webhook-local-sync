from app.auth import BearerAuth
from fastapi import HTTPException
import sys

def test():
    auth = BearerAuth(token="secret-token")

    # Test valid token
    try:
        assert auth.verify_token("secret-token") is True
        print("PASS: valid token")
    except Exception as e:
        print(f"FAIL: valid token - {e}")
        return False

    # Test invalid token
    try:
        auth.verify_token("wrong-token")
        print("FAIL: invalid token did not raise")
        return False
    except HTTPException as e:
        assert e.status_code == 401
        print("PASS: invalid token raised 401")
    except Exception as e:
        print(f"FAIL: invalid token raised wrong exception - {e}")
        return False

    # Test extraction and verification
    try:
        assert auth.verify("Bearer secret-token") is True
        print("PASS: Bearer header verification")
    except Exception as e:
        print(f"FAIL: Bearer header verification - {e}")
        return False

    return True

if __name__ == "__main__":
    if test():
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Tests failed!")
        sys.exit(1)
