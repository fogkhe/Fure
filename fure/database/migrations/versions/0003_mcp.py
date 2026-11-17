"""Explicit function scopes for API keys and MCP access."""

import json

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "api_keys",
        sa.Column("function_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    roles = sa.table(
        "roles",
        sa.column("id", sa.Uuid()),
        sa.column("permissions", sa.JSON()),
        sa.column("protected", sa.Boolean()),
    )
    # The protected administrator role always has all permissions. Keep this
    # snapshot independent of the runtime enum and usable in offline migrations.
    op.execute(
        roles.update()
        .where(roles.c.protected.is_(True))
        .values(
            permissions=op.inline_literal(
                json.dumps(
                    [
                        "functions.read",
                        "functions.create",
                        "functions.update",
                        "functions.delete",
                        "functions.publish",
                        "functions.run",
                        "runs.read",
                        "runs.read_all",
                        "runs.cancel",
                        "runs.cancel_all",
                        "users.manage",
                        "roles.manage",
                        "keys.manage",
                        "mcp.access",
                    ]
                )
            )
        )
    )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "UPDATE roles SET permissions = COALESCE((SELECT json_agg(value) FROM json_array_elements_text(roles.permissions) AS p(value) WHERE value != 'mcp.access'), '[]'::json)"
        )
    else:
        op.execute(
            "UPDATE roles SET permissions = (SELECT json_group_array(value) FROM json_each(roles.permissions) WHERE value != 'mcp.access')"
        )
    op.drop_column("api_keys", "function_ids")
