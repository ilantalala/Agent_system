from datetime import datetime

from sqlalchemy import DateTime,ForeignKey, String, func, Text,JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    openai_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    anthropic_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    agents: Mapped[list["Agent"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    
class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )    
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    created_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    draft_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The version real traffic uses. use_alter: agents and agent_versions point
    # at each other, so this FK is added after both tables exist.
    live_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_versions.id", use_alter=True, ondelete="SET NULL"),
        nullable=True,
    )
    owner: Mapped["User"] = relationship(back_populates="agents")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent",
        foreign_keys="AgentVersion.agent_id",
        cascade="all, delete-orphan",
        order_by="AgentVersion.number",
    )
    # post_update: set this pointer in a second UPDATE, after the version row exists.
    live_version: Mapped["AgentVersion | None"] = relationship(
        foreign_keys=[live_version_id], post_update=True
    )
    draft_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Read-only views of the live version, so AgentRead keeps its system_prompt field.
    @property
    def system_prompt(self) -> str | None:
        return self.live_version.system_prompt if self.live_version else None

    @property
    def live_version_number(self) -> int | None:
        return self.live_version.number if self.live_version else None


class AgentVersion(Base):
    # An immutable snapshot of a finalized prompt: never updated, only added.
    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    number: Mapped[int] = mapped_column(nullable=False)  # 1, 2, 3… per agent
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    agent: Mapped["Agent"] = relationship(
        back_populates="versions", foreign_keys=[agent_id]
    )

    @property
    def is_live(self) -> bool:
        return self.agent.live_version_id == self.id
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, server_default="architect")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    agent: Mapped["Agent"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
