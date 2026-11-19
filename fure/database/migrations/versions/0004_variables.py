"""Shared variables and their catalogue permissions."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "variables",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("secret", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "UPDATE roles SET permissions = (permissions::jsonb || "
            '\'["variables.read", "variables.manage"]\'::jsonb)::json WHERE protected'
        )
    else:
        op.execute(
            "UPDATE roles SET permissions = json_insert("
            "json_insert(permissions, '$[#]', 'variables.read'), "
            "'$[#]', 'variables.manage') WHERE protected"
        )


def downgrade():
    for table in ("roles", "api_keys"):
        remaining = "value NOT IN ('variables.read', 'variables.manage')"
        if op.get_bind().dialect.name == "postgresql":
            op.execute(
                f"UPDATE {table} SET permissions = COALESCE((SELECT json_agg(value) "
                f"FROM json_array_elements_text({table}.permissions) AS p(value) "
                f"WHERE {remaining}), '[]'::json)"
            )
        else:
            op.execute(
                f"UPDATE {table} SET permissions = (SELECT json_group_array(value) "
                f"FROM json_each({table}.permissions) WHERE {remaining})"
            )
    op.drop_table("variables")
