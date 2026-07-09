from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import hash_password, verify_password, create_access_token, get_current_user, get_current_user_unchecked, oauth2_scheme, require_role
from config import settings
from database import get_db
from models import RevokedToken, User, UserRole
from rate_limit import limiter, token_or_ip

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "viewer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    force_password_change: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    force_password_change: bool

    class Config:
        from_attributes = True


def _as_utc(dt):
    """SQLite (tests) returns naive datetimes for DateTime(timezone=True); Postgres returns aware."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.post("/login", response_model=TokenResponse)
@limiter.limit(lambda *_: settings.login_rate_limit)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username, User.is_active == True).first()
    now = datetime.now(timezone.utc)

    # Account lockout (Step 1.3): rejected before password verification so a
    # locked account leaks no signal about whether the password was correct.
    if user is not None:
        locked_until = _as_utc(user.locked_until)
        if locked_until and locked_until > now:
            retry_after = int((locked_until - now).total_seconds()) + 1
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account temporarily locked after repeated failed logins",
                headers={"Retry-After": str(retry_after)},
            )

    if not user or not verify_password(form_data.password, user.hashed_password):
        if user is not None:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= settings.login_lockout_threshold:
                user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
                user.failed_login_count = 0  # fresh threshold once the lockout expires
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if user.failed_login_count or user.locked_until is not None:
        user.failed_login_count = 0
        user.locked_until = None
        db.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "ver": user.token_version or 0})
    return {"access_token": token, "token_type": "bearer", "force_password_change": user.force_password_change}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Revoke the presented token (Step 1.4). Requires only a validly signed
    token — works even mid forced-password-change."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    jti = payload.get("jti")
    if jti:
        now = datetime.now(timezone.utc)
        # Opportunistic prune: denylist rows past their token's natural expiry
        # can never match a live token again.
        db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete()
        db.merge(RevokedToken(jti=jti, expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)))
        db.commit()


@router.post("/change-password", response_model=TokenResponse)
@limiter.limit(lambda *_: settings.login_rate_limit, key_func=token_or_ip)
def change_password(
    request: Request,
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_unchecked),
):
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(req.new_password)
    current_user.force_password_change = False
    # Step 1.4: invalidate every previously issued token for this user, then
    # return a fresh one so the current session continues seamlessly.
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()
    token = create_access_token({"sub": current_user.email, "role": current_user.role, "ver": current_user.token_version})
    return {"access_token": token, "token_type": "bearer", "force_password_change": False}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    req: RegisterRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if req.role not in [r.value for r in UserRole]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {req.role}")
    user = User(email=req.email, hashed_password=hash_password(req.password), role=req.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    return db.query(User).order_by(User.id).all()


class AssignableUser(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True


@router.get("/users/assignable", response_model=list[AssignableUser])
def list_assignable_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    """Minimal active-user list for alert assignment dropdowns (editor/admin)."""
    return db.query(User).filter(User.is_active == True).order_by(User.email).all()


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
