"""Move live prompts into agent versions.

Revision ID: a1c3e5f7b9d2
Revises: 300716e8c355

Backfill each non-null prompt as version 1 and make it live before dropping
the old column. Downgrade keeps only the live prompt; older versions are lost.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c3e5f7b9d2"
down_revision: Union[str, Sequence[str], None] = "300716e8c355"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create versions and preserve existing live prompts as version 1."""
    op.create_table(
        "agent_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "number"),
    )
    op.create_index(op.f("ix_agent_versions_agent_id"), "agent_versions", ["agent_id"])
    op.add_column("agents", sa.Column("live_version_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "agents_live_version_id_fkey", "agents", "agent_versions",
        ["live_version_id"], ["id"], ondelete="SET NULL",
    )
    op.execute(
        "INSERT INTO agent_versions (agent_id, number, system_prompt) "
        "SELECT id, 1, system_prompt FROM agents WHERE system_prompt IS NOT NULL"
    )
    op.execute(
        "UPDATE agents SET live_version_id = v.id FROM agent_versions v "
        "WHERE v.agent_id = agents.id AND v.number = 1"
    )
    op.drop_column("agents", "system_prompt")


def downgrade() -> None:
    """Restore only the live prompt; dropping versions loses all older prompts."""
    op.add_column("agents", sa.Column("system_prompt", sa.Text(), nullable=True))
    op.execute(
        "UPDATE agents SET system_prompt = v.system_prompt FROM agent_versions v "
        "WHERE v.id = agents.live_version_id"
    )
    op.drop_constraint("agents_live_version_id_fkey", "agents", type_="foreignkey")
    op.drop_column("agents", "live_version_id")
    op.drop_index(op.f("ix_agent_versions_agent_id"), table_name="agent_versions")
    op.drop_table("agent_versions")
