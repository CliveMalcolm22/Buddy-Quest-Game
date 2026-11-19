from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.auth import AccountResponse, LoginRequest, TokenResponse, UserCreate
from app.security import create_access_token, digest_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthSession:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_digest = digest_access_token(credentials.credentials)
    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_digest == token_digest))
    now = datetime.now(timezone.utc)
    if auth_session is None or auth_session.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not auth_session.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive account.")
    return auth_session


def get_current_user(auth_session: AuthSession = Depends(get_current_session)) -> User:
    return auth_session.user


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    try:
        db.flush()
        return _issue_token(db, user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email is already registered.") from exc


@router.post("/login", response_model=TokenResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_token(db, user)


@router.get("/me", response_model=AccountResponse)
def read_account(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user(
    response: Response,
    auth_session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    db.delete(auth_session)
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT


def _issue_token(db: Session, user: User) -> dict[str, str]:
    token = create_access_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    db.add(AuthSession(user_id=user.id, token_digest=digest_access_token(token), expires_at=expires_at))
    db.commit()
    return {"access_token": token, "token_type": "bearer"}
