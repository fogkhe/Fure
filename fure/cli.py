"""Administrative operations: python -m fure.cli create-admin <username>."""

import argparse
import asyncio
import getpass
import sys

from pydantic import TypeAdapter

from fure.api.v1.schemas.auth import Username
from fure.database.connection import Database
from fure.services.auth import AuthService
from fure.services.errors import ServiceError
from fure.settings import settings


async def create_admin(username, password):
    database = Database(settings.database_url.get_secret_value())
    try:
        await database.migrate()
        user = await AuthService(database).create_first_admin(username, password)
        print(f"Administrator {user.username!r} created.")
    finally:
        await database.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    create = subcommands.add_parser("create-admin")
    create.add_argument("username", type=TypeAdapter(Username).validate_python)
    create.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read one password line from stdin",
    )
    args = parser.parse_args()
    password = (
        sys.stdin.readline().rstrip("\r\n")
        if args.password_stdin
        else getpass.getpass("Password (12–256 characters): ")
    )
    if not args.password_stdin and password != getpass.getpass("Confirm password: "):
        parser.error("Passwords do not match")
    try:
        asyncio.run(create_admin(args.username, password))
    except ServiceError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
