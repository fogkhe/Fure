"""Link tool runs to their parent agent run."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("parent_run_id", sa.Uuid()))
        batch.add_column(sa.Column("tool_call_index", sa.Integer()))
        batch.create_foreign_key(
            "fk_runs_parent_run", "runs", ["parent_run_id"], ["id"]
        )
        batch.create_check_constraint(
            "ck_runs_tool_call",
            "(parent_run_id IS NULL AND tool_call_index IS NULL) OR "
            "(parent_run_id IS NOT NULL AND tool_call_index IS NOT NULL AND tool_call_index > 0)",
        )
        batch.create_index(
            "ix_runs_parent_call", ["parent_run_id", "tool_call_index"], unique=True
        )


def downgrade():
    with op.batch_alter_table("runs") as batch:
        batch.drop_index("ix_runs_parent_call")
        batch.drop_constraint("ck_runs_tool_call", type_="check")
        batch.drop_constraint("fk_runs_parent_run", type_="foreignkey")
        batch.drop_column("tool_call_index")
        batch.drop_column("parent_run_id")
