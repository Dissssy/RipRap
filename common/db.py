import codecs
import hashlib
import math
from time import time
from databases import Database

from config import DATABASE_URL


async def _create_db_connection() -> Database:
    db = Database(DATABASE_URL)
    await db.connect()
    return db


async def _is_ratelimited(app, endpoint_id, t, maxuses, snowflake):
    await app.db.execute(
        f"""DELETE FROM ratelimit WHERE apiendpoint = :apiendpoint AND timecalled <= :timecalled""",
        values={"apiendpoint": endpoint_id, "timecalled": math.floor(time()) - t},
    )

    limited = await app.db.fetch_val(
        f"""SELECT COUNT(*) FROM ratelimit WHERE snowflake = :snowflake AND apiendpoint = :apiendpoint""",
        values={"snowflake": snowflake, "apiendpoint": endpoint_id},
    )

    if limited < maxuses:
        limited = await app.db.fetch_val(
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


async def _fetch_user_data(app, snowflake=None, username=None, field="snowflake"):
    if snowflake is not None:
        value = [f"""snowflake = :snowflake""", {"snowflake": snowflake}]
    elif username is not None:
        value = [f"""username = :username""", {"username": username}]
    try:
        return await app.db.fetch_val(
            f"""SELECT {field} FROM users WHERE {value[0]}""",
            values=value[1],
        )
    except Exception as e:
        return e


async def _add_user_token(app, user_snowflake: str, session_name: str) -> str:
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


async def _remove_user_token(app, token: str) -> None | Exception:
    values = {"token": token}
    return await app.db.execute(
        f"""DELETE FROM tokens WHERE token = :token RETURNING session_name""",
        values=values,
    )


async def _get_snowflake_from_token(app, token: str) -> str:
    return await app.db.fetch_val(
        f"""SELECT snowflake FROM tokens WHERE token = :token""",
        values={"token": token},
    )


async def _get_all_tokens(app, snowflake: str) -> list:
    tokens = await app.db.fetch_all(
        f"""SELECT (token, session_name) FROM tokens WHERE snowflake = :snowflake""",
        values={"snowflake": snowflake},
    )
    return [{"token": x["row"][0], "session_name": x["row"][1]} for x in tokens]
