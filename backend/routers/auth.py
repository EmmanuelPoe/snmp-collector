from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import hash_password, verify_password, create_access_token, get_current_user, get_current_user_unchecked, require_role
from database import get_db
from models import User, UserRole

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


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username, User.is_active == True).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "force_password_change": user.force_password_change}


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_unchecked),
):
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(req.new_password)
    current_user.force_password_change = False
    db.commit()


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
