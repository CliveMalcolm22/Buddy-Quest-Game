from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    friendships: Mapped[list["Friendship"]] = relationship(
        back_populates="user",
        foreign_keys="Friendship.user_id",
        cascade="all, delete-orphan",
    )
    friend_links: Mapped[list["Friendship"]] = relationship(
        back_populates="friend",
        foreign_keys="Friendship.friend_id",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    streak: Mapped["Streak"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    point_events: Mapped[list["PointEvent"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    help_requests: Mapped[list["HelpRequest"]] = relationship(
        back_populates="requester",
        foreign_keys="HelpRequest.requester_id",
        cascade="all, delete-orphan",
    )
    auth_sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
