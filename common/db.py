import codecs
import hashlib
import math
from time import time
import uuid
from databases import Database
import quart

from config import DATABASE_URL


async def _create_db_connection() -> Database:
    db = Database(DATABASE_URL)
    await db.connect()
    return db


async def _is_ratelimited(db: Database, endpoint_id, t, maxuses, snowflake):
    await db.execute(
        f"""DELETE FROM ratelimit WHERE apiendpoint = :apiendpoint AND timecalled <= :timecalled""",
        values={"apiendpoint": endpoint_id, "timecalled": math.floor(time()) - t},
    )

    limited = await db.fetch_val(
        f"""SELECT COUNT(*) FROM ratelimit WHERE snowflake = :snowflake AND apiendpoint = :apiendpoint""",
        values={"snowflake": snowflake, "apiendpoint": endpoint_id},
    )

    if limited < maxuses:
        limited = await db.fetch_val(
            f"""INSERT INTO ratelimit (snowflake, timecalled, apiendpoint) VALUES (:snowflake, :timecalled, :apiendpoint)""",
            values={
                "snowflake": snowflake,
                "timecalled": math.floor(time()),
                "apiendpoint": endpoint_id,
            },
        )
        return False
    else:
        return True


async def _fetch_user_data(
    db: Database, snowflake=None, username=None, field="snowflake"
):
    if snowflake is not None:
        value = [f"""snowflake = :snowflake""", {"snowflake": snowflake}]
    elif username is not None:
        value = [f"""username = :username""", {"username": username}]
    else:
        return None
    try:
        return await db.fetch_val(
            f"""SELECT {field} FROM users WHERE {value[0]}""",
            values=value[1],
        )
    except Exception as e:
        return e


async def _add_user_token(
    app: quart.app, user_snowflake: str, session_name: str
) -> str:
    return await app.db.fetch_val(
        f"""INSERT INTO tokens (token, snowflake, session_name) VALUES (:token, :snowflake, :session_name) RETURNING token""",
        values={
            "token": hashlib.sha512(
                codecs.encode(
                    f"{app.uuid(16).bytes.hex()} {app.uuid(8192).bytes.hex()}", "ascii"
                )
            ).hexdigest(),
            "snowflake": user_snowflake,
            "session_name": session_name,
        },
    )


async def _remove_user_token(db: Database, token: str) -> None | Exception:
    values = {"token": token}
    return await db.execute(
        f"""DELETE FROM tokens WHERE token = :token RETURNING session_name""",
        values=values,
    )


async def _get_snowflake_from_token(db: Database, token: str) -> str | None:
    return await db.fetch_val(
        f"""SELECT snowflake FROM tokens WHERE token = :token""",
        values={"token": token},
    )


async def _get_all_tokens(db: Database, snowflake: str) -> list:
    tokens = await db.fetch_all(
        f"""SELECT (token, session_name) FROM tokens WHERE snowflake = :snowflake""",
        values={"snowflake": snowflake},
    )
    return [{"token": x["row"][0], "session_name": x["row"][1]} for x in tokens]


async def _delete_user(db: Database, snowflake: str) -> None:
    await db.execute(
        """DELETE FROM users WHERE snowflake = :snowflake""",
        values={"snowflake": snowflake},
    )
    sessions = await _get_all_tokens(db, snowflake)
    for session in sessions:
        await _remove_user_token(db, session["token"])
    await db.execute(
        """DELETE FROM ratelimit WHERE snowflake = :snowflake""",
        values={"snowflake": snowflake},
    )


async def _is_user(db: Database, snowflake: str) -> bool:
    if (
        await db.fetch_val(
            """SELECT * FROM users WHERE snowflake = :snowflake""", values={}
        )
        is None
    ):
        return False
    return True


async def _is_channel(db: Database, snowflake: str) -> bool:
    if (
        await db.fetch_val(
            """SELECT * FROM channels WHERE snowflake = :snowflake""", values={}
        )
        is None
    ):
        return False
    return True


async def _get_user_servers(db: Database, snowflake: str) -> list[str]:
    servers = await db.fetch_all(
        """SELECT server_snowflake FROM server_access WHERE user_snowflake = :user_snowflake""",
        values={"user_snowflake": snowflake},
    )
    return [x[0] for x in servers]


async def _grant_server_access(
    db: Database, server_snowflake: str, user_snowflake: str
):
    return await db.execute(
        """INSERT INTO server_access (user_snowflake, server_snowflake) VALUES (:user_snowflake, :server_snowflake) returning server_snowflake""",
        values={"user_snowflake": user_snowflake, "server_snowflake": server_snowflake},
    )


async def _has_access_to_server(
    db: Database, server_snowflake: str, user_snowflake: str
):
    if (
        await db.execute(
            """SELECT COUNT(*) FROM server_access WHERE user_snowflake = :user_snowflake AND server_snowflake = :server_snowflake""",
            values={
                "user_snowflake": user_snowflake,
                "server_snowflake": server_snowflake,
            },
        )
        > 0
    ):
        return True
    return False


async def _get_server_info(db: Database, server_snowflake: str):
    baseinfo = await db.fetch_one(
        """SELECT * FROM servers WHERE snowflake = :snowflake""",
        values={"snowflake": server_snowflake},
    )
    return {
        "name": baseinfo["name"],
        "picture": baseinfo["picture"],
        "owner_snowflake": baseinfo["owner_snowflake"],
        "snowflake": baseinfo["snowflake"],
        "channels": [
            x[0]
            for x in await db.fetch_all(
                """SELECT channel_snowflake FROM server_channels WHERE server_snowflake = :server_snowflake""",
                values={"server_snowflake": server_snowflake},
            )
        ],
    }
