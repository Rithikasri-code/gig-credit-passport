from fastapi import Depends, HTTPException, Header

from app.core.security import decode_access_token


async def get_current_user_id(authorization: str = Header(None)) -> str:
    """
    Expects 'Authorization: Bearer <token>'. Returns the authenticated
    user's id. Every protected route depends on this instead of trusting
    a user_id passed in the URL/body.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header.")

    token = authorization.removeprefix("Bearer ").strip()
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(401, "Invalid or expired token.")
    return user_id


def require_self(path_user_id: str, current_user_id: str) -> None:
    """
    Call this in any route that also takes a user_id in the path/body,
    to make sure a worker can only ever act on their own data.
    """
    if path_user_id != current_user_id:
        raise HTTPException(403, "You can only access your own data.")
