"""Functions, immutable revisions and execution history."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "functions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("revision_id", sa.Uuid()),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["revisions.id"],
            name="fk_functions_revision",
            use_alter=True,
        ),
    )
    op.create_index(
        "uq_functions_active_name",
        "functions",
        ["name"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_functions_created", "functions", ["created_at", "id"])
    op.create_table(
        "revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "function_id", sa.Uuid(), sa.ForeignKey("functions.id"), nullable=False
        ),
        sa.Column("implementation", sa.JSON(), nullable=False),
        sa.Column("runner_options", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_functions_revision", "functions", "revisions", ["revision_id"], ["id"]
        )
    op.create_index(
        "ix_revisions_function_created",
        "revisions",
        ["function_id", "created_at", "id"],
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "revision_id", sa.Uuid(), sa.ForeignKey("revisions.id"), nullable=False
        ),
        sa.Column("input", sa.JSON()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("output", sa.JSON()),
        sa.Column("meta", sa.JSON()),
        sa.Column("duration", sa.Float()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("worker_id", sa.Uuid()),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_runs_status",
        ),
        sa.CheckConstraint(
            "duration IS NULL OR duration >= 0", name="ck_runs_duration"
        ),
    )
    op.create_index(
        "ix_runs_revision_created", "runs", ["revision_id", "created_at", "id"]
    )
    op.create_index("ix_runs_status_heartbeat", "runs", ["status", "heartbeat_at"])
    op.create_index("ix_runs_created", "runs", ["created_at", "id"])


def downgrade():
    op.drop_table("runs")
    op.execute(sa.text("UPDATE functions SET revision_id = NULL"))
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_functions_revision", "functions", type_="foreignkey")
    op.drop_table("revisions")
    op.drop_table("functions")
