import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import RevokedToken, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    # jti (Step 1.4): unique token id so an individual token can be revoked at logout.
    return jwt.encode(
        {**data, "exp": expire, "jti": uuid.uuid4().hex},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _resolve_user(token: str, db: Session) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email: Optional[str] = payload.get("sub")
        if not email:
            raise exc
    except JWTError:
        raise exc
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise exc
    # Token lifecycle (Step 1.4): reject version-stale tokens (issued before the
    # user's last password change) and revoked (logged-out) tokens. Tokens issued
    # before this feature carry no "ver" claim and default to version 0.
    if payload.get("ver", 0) != (user.token_version or 0):
        raise exc
    jti = payload.get("jti")
    if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise exc
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = _resolve_user(token, db)
    if user.force_password_change:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="password_change_required",
        )
    return user


def get_current_user_unchecked(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Like get_current_user but skips the force_password_change check — for change-password endpoint."""
    return _resolve_user(token, db)


def require_role(*roles: str):
    """Return a FastAPI dependency that enforces one of the given roles."""
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return dependency


def require_manager_key(authorization: str = Header(None)) -> bool:
    """Validate Authorization: Bearer <MANAGER_API_KEY> for service-to-service calls."""
    expected = f"Bearer {settings.manager_api_key}"
    if not secrets.compare_digest(authorization or "", expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid manager API key")
    return True
