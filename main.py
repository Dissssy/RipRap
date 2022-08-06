import sys

from quart_cors import cors

sys.path.append(".")

import asyncio
import zlib
from quart import Quart
from quart_schema import (
    QuartSchema,
)
from snowflake import SnowflakeGenerator
import json
import uuid

import config

from common.primitive import Primitive
from common.db import _create_db_connection

import bp.auth, bp.server, bp.channel

app = Quart(__name__)
QuartSchema(app)
app.config.update(
    {
        "DATABASE_URL": config.DATABASE_URL,
        "SMTP": {
            "SERVER": config.SMTP_SERVER,
            "PORT": config.SMTP_PORT,
            "USER": config.SMTP_USER,
            "PASSWORD": config.SMTP_PASSWORD,
        },
    }
)
app = cors(app, allow_origin="*")


def register_blueprints(app: Quart):
    blueprints = [bp.auth.bp, bp.server.bp, bp.channel.bp]
    for blueprint in blueprints:
        app.register_blueprint(blueprint, url_prefix=f"/api/{blueprint.name}")


register_blueprints(app)


def encode_json(thing) -> bytes:
    return zlib.compress(bytes(json.dumps(thing), "utf-8"))


def decode_json(nibble: bytes):
    return json.loads(zlib.decompress(nibble).decode("utf-8"))


# @app.route("/")
# async def index():
#     count_users = await app.db.fetch_val("SELECT COUNT(*) FROM users")
#     return f"There are {count_users} users registered!"


@app.before_serving
async def startup() -> None:
    app.db = await _create_db_connection()
    app.snowflake_gen = SnowflakeGenerator(0)
    app.uuid = uuid.uuid1


@app.after_serving
async def shutdown() -> None:
    pass


@app.cli.command("init_db")
def init_db() -> None:
    async def _inner() -> None:
        db = await _create_db_connection()
        async with await app.open_resource("schema.sql", "r") as file:
            for query in (await file.read()).split(";"):
                await db.fetch_val(f"{query};")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_inner())


if __name__ == "__main__":
    app.run()