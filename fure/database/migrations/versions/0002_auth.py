"""Users, roles, credentials, public functions and run ownership."""

import json
from datetime import UTC, datetime
from uuid import uuid7

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Migration snapshots must not depend on the application's permission enum.
PERMISSIONS = [
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
]


def upgrade():
    roles = op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("protected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            sa.Uuid(),
            sa.ForeignKey("roles.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_table(
        "sessions",
        sa.Column("secret_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.add_column(
        "functions",
        sa.Column("public", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Batch mode is needed to add foreign keys to existing SQLite tables.
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("user_id", sa.Uuid()))
        batch.add_column(sa.Column("api_key_id", sa.Uuid()))
        batch.create_foreign_key("fk_runs_user", "users", ["user_id"], ["id"])
        batch.create_foreign_key("fk_runs_api_key", "api_keys", ["api_key_id"], ["id"])
        batch.create_index("ix_runs_user_created", ["user_id", "created_at", "id"])
    now = datetime.now(UTC)
    seeds = [
        {
            "id": uuid7(),
            "name": "admin",
            "permissions": PERMISSIONS,
            "protected": True,
            "created_at": now,
        },
        {
            "id": uuid7(),
            "name": "editor",
            "permissions": [
                p
                for p in PERMISSIONS
                if p.startswith("functions.") and p != "functions.publish"
            ]
            + ["runs.read", "runs.cancel", "keys.manage"],
            "protected": False,
            "created_at": now,
        },
        {
            "id": uuid7(),
            "name": "runner",
            "permissions": [
                "functions.read",
                "functions.run",
                "runs.read",
                "runs.cancel",
                "keys.manage",
            ],
            "protected": False,
            "created_at": now,
        },
    ]
    for seed in seeds:
        seed["permissions"] = op.inline_literal(json.dumps(seed["permissions"]))
    op.bulk_insert(roles, seeds, multiinsert=False)


def downgrade():
    with op.batch_alter_table("runs") as batch:
        batch.drop_index("ix_runs_user_created")
        batch.drop_constraint("fk_runs_api_key", type_="foreignkey")
        batch.drop_constraint("fk_runs_user", type_="foreignkey")
        batch.drop_column("api_key_id")
        batch.drop_column("user_id")
    op.drop_column("functions", "public")
    for table in ("sessions", "api_keys", "user_roles", "users", "roles"):
        op.drop_table(table)
