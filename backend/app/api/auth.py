import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.models.models import User
from app.schemas.schemas import UserRegister, UserLogin, UserResponse, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def get_or_create_guest_user(db: Session, guest_id: Optional[str] = None) -> User:
    if guest_id:
        guest = db.query(User).filter(User.id == guest_id).first()
        if guest:
            return guest
        uname = f"guest_{guest_id}"
        if len(uname) > 50:
            uname = f"guest_{guest_id[-16:]}"
        if db.query(User).filter(User.username == uname).first():
            uname = f"guest_{uuid.uuid4().hex[:12]}"
        guest = User(
            id=guest_id,
            username=uname,
            is_guest=True
        )
        db.add(guest)
        try:
            db.commit()
            db.refresh(guest)
            return guest
        except Exception:
            db.rollback()
            guest = db.query(User).filter(User.id == guest_id).first()
            if guest:
                return guest
            raise

    guest = db.query(User).filter(User.username == "guest_user").first()
    if not guest:
        guest = User(
            id=str(uuid.uuid4()),
            username="guest_user",
            is_guest=True
        )
        db.add(guest)
        db.commit()
        db.refresh(guest)
    return guest

def get_current_user(
    authorization: Optional[str] = Header(None),
    x_guest_id: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Returns authenticated user, or falls back to local guest user."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            user = db.query(User).filter(User.id == payload["sub"]).first()
            if user:
                return user
    return get_or_create_guest_user(db, guest_id=x_guest_id)

@router.post("/register", response_model=TokenResponse)
def register(req: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        is_guest=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "username": user.username})
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))

@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    token = create_access_token({"sub": user.id, "username": user.username})
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))

@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)

@router.get("/guest-token", response_model=TokenResponse)
def get_guest_token(
    x_guest_id: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    guest = get_or_create_guest_user(db, guest_id=x_guest_id)
    token = create_access_token({"sub": guest.id, "username": guest.username})
    return TokenResponse(access_token=token, user=UserResponse.model_validate(guest))
