import codecs
import hashlib
import math
from time import time
from typing import Optional
from databases import Database
import quart

from config import DATABASE_URL


async def _create_db_connection() -> Database:
    db = Database(DATABASE_URL)
    await db.connect()
    return db


async def _is_ratelimited(
    db: Database, endpoint_id: str, t: int, maxuses: int, snowflake: str
):
    return 0
    await db.execute(
        f"""DELETE FROM ratelimit WHERE apiendpoint = :apiendpoint AND timecalled <= :timecalled""",
        values={"apiendpoint": endpoint_id, "timecalled": math.floor(time()) - t},
    )

    limited = await db.fetch_val(
        f"""SELECT COUNT(*) FROM ratelimit WHERE snowflake = :snowflake AND apiendpoint = :apiendpoint""",
        values={"snowflake": int(snowflake), "apiendpoint": endpoint_id},
    )

    if limited < maxuses:
        limited = await db.fetch_val(
            f"""INSERT INTO ratelimit (snowflake, timecalled, apiendpoint) VALUES (:snowflake, :timecalled, :apiendpoint)""",
            values={
                "snowflake": int(snowflake),
                "timecalled": math.floor(time()),
                "apiendpoint": endpoint_id,
            },
        )
        return 0
    else:
        timecalled = await db.fetch_one(
            f"""SELECT timecalled FROM ratelimit WHERE snowflake = :snowflake AND apiendpoint = :apiendpoint LIMIT 1""",
            values={"snowflake": int(snowflake), "apiendpoint": endpoint_id},
        )
        return time() - timecalled


async def _fetch_user_data(
    db: Database, snowflake=None, username=None, field="snowflake"
):
    if snowflake is not None:
        value = [f"""snowflake = :snowflake""", {"snowflake": int(snowflake)}]
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
    info = await app.db.fetch_val(
        f"""INSERT INTO tokens (token, snowflake, session_name) VALUES (:token, :snowflake, :session_name) RETURNING (token, session_name)""",
        values={
            "token": hashlib.sha512(
                codecs.encode(
                    f"{app.uuid(16).bytes.hex()} {app.uuid(8192).bytes.hex()}", "ascii"
                )
            ).hexdigest(),
            "snowflake": int(user_snowflake),
            "session_name": session_name,
        },
    )
    return {
        "token": info[0],
        "session_name": info[1]
    }


async def _remove_user_token(db: Database, token: str):
    values = {"token": token}
    return await db.execute(
        f"""DELETE FROM tokens WHERE token = :token RETURNING session_name""",
        values=values,
    )


async def _get_snowflake_from_token(db: Database, token: str):
    snowflake = await db.fetch_val(
        f"""SELECT snowflake FROM tokens WHERE token = :token""",
        values={"token": token},
    )
    if snowflake is None:
        return None
    else:
        return str(snowflake)


async def _get_all_tokens(db: Database, snowflake: str):
    tokens = await db.fetch_all(
        f"""SELECT (token, session_name) FROM tokens WHERE snowflake = :snowflake""",
        values={"snowflake": int(snowflake)},
    )
    return [{"token": x["row"][0], "session_name": x["row"][1]} for x in tokens]


async def _delete_user(db: Database, snowflake: str):
    await db.execute(
        """DELETE FROM users WHERE snowflake = :snowflake""",
        values={"snowflake": int(snowflake)},
    )
    sessions = await _get_all_tokens(db, snowflake)
    for session in sessions:
        await _remove_user_token(db, session["token"])
    await _cleanup(db, "ratelimit", "snowflake", int(snowflake))
    await _cleanup(db, "server_access", "user_snowflake", int(snowflake))
    await _cleanup(db, "channel_access", "user_snowflake", int(snowflake))


async def _cleanup(db: Database, table: str, match_value: str, value):
    await db.execute(
        f"""DELETE FROM {table} WHERE {match_value} = :{match_value}""",
        values={match_value: value},
    )


async def _is_user(db: Database, snowflake: str) -> bool:
    if (
        await db.fetch_val(
            """SELECT * FROM users WHERE snowflake = :snowflake""",
            values={"snowflake": int(snowflake)},
        )
        is None
    ):
        return False
    return True


async def _is_channel(db: Database, snowflake: str):
    if (
        await db.fetch_val(
            """SELECT * FROM channels WHERE snowflake = :snowflake""",
            values={"snowflake": int(snowflake)},
        )
        is None
    ):
        return False
    return True


async def _get_user_servers(db: Database, snowflake: str):
    servers = await db.fetch_all(
        """SELECT server_snowflake FROM server_access WHERE user_snowflake = :user_snowflake""",
        values={"user_snowflake": int(snowflake)},
    )
    serverlist = [str(x[0]) for x in servers]
    serverlist.append("0")
    finallist = []
    for server in serverlist:
        finallist.append(await _get_server_info(db, server))
    return finallist


async def _grant_server_access(
    db: Database, server_snowflake: str, user_snowflake: str
):
    return await db.execute(
        """INSERT INTO server_access (user_snowflake, server_snowflake) VALUES (:user_snowflake, :server_snowflake) returning server_snowflake""",
        values={
            "user_snowflake": int(user_snowflake),
            "server_snowflake": int(server_snowflake),
        },
    )


async def _has_access_to_server(
    db: Database, server_snowflake: str, user_snowflake: str
):
    if server_snowflake == "0":
        return True
    if (
        await db.execute(
            """SELECT COUNT(*) FROM server_access WHERE user_snowflake = :user_snowflake AND server_snowflake = :server_snowflake""",
            values={
                "user_snowflake": int(user_snowflake),
                "server_snowflake": int(server_snowflake),
            },
        )
        > 0
    ):
        return True
    return False


async def _get_server_info(db: Database, server_snowflake: str):
    baseinfo = await db.fetch_one(
        """SELECT * FROM servers WHERE snowflake = :snowflake""",
        values={"snowflake": int(server_snowflake)},
    )
    if baseinfo is not None:
        channellist = [
            x[0]
            for x in await db.fetch_all(
                """SELECT channel_snowflake FROM server_channels WHERE server_snowflake = :server_snowflake""",
                values={"server_snowflake": int(server_snowflake)},
            )
        ]
        finalchannellist = []
        for channel in channellist:
            finalchannellist.append(await _get_channel_info(db, channel))
        return {
            "name": baseinfo["name"],
            "picture": baseinfo["picture"],
            "owner": await _get_user_info(db, str(baseinfo["owner_snowflake"])),
            "snowflake": str(baseinfo["snowflake"]),
            "channels": finalchannellist,
        }
    return None


async def _delete_server(db: Database, server_snowflake: str, user_snowflake: str):
    response = await _is_owner(db, int(server_snowflake), int(user_snowflake))
    if type(response) is not str:
        await db.execute(
            """DELETE FROM servers WHERE snowflake = :snowflake""",
            values={"snowflake": int(server_snowflake)},
        )
        await _cleanup(db, "server_channels", "server_snowflake", int(server_snowflake))
        info = await _get_server_info(db, int(server_snowflake))
        for channel in info["channels"]:
            await _delete_channel(db, int(channel))
        await _cleanup(db, "server_access", "server_snowflake", int(server_snowflake))
        return None
    else:
        return response


async def _delete_channel(
    db: Database,
    channel_snowflake: str,
    server_snowflake: str = "validated",
    user_snowflake: str = "validated",
):
    if server_snowflake == "validated" and user_snowflake == "validated":
        return await _remove_and_clean_up_channel(db, int(channel_snowflake))
    else:
        response = await _is_owner(db, int(server_snowflake), int(user_snowflake))
        if type(response) is not str:
            return await _remove_and_clean_up_channel(db, int(channel_snowflake))
        else:
            return response


async def _remove_and_clean_up_channel(db: Database, channel_snowflake: str):
    if (
        await db.fetch_one(
            """SELECT server_snowflake FROM server_channels WHERE channel_snowflake = :channel_snowflake""",
            values={"channel_snowflake", int(channel_snowflake)},
        )
        is None
    ):
        await db.execute(
            """DELETE FROM channels WHERE snowflake = :snowflake""",
            values={"snowflake", int(channel_snowflake)},
        )
        await _cleanup(db, "messages", "channel_snowflake", int(channel_snowflake))
        return None
    else:
        return "Channel exists within another server"


async def _get_channel_info(db: Database, channel_snowflake: str):
    baseinfo = await db.fetch_one(
        """SELECT * FROM channels WHERE snowflake = :snowflake""",
        values={"snowflake": int(channel_snowflake)},
    )
    if baseinfo is not None:
        return {
            "name": baseinfo["name"],
            "picture": baseinfo["picture"],
            "snowflake": str(baseinfo["snowflake"]),
            "message_count": await db.fetch_val(
                """SELECT COUNT(*) FROM messages WHERE channel_snowflake = :channel_snowflake""",
                values={"channel_snowflake": int(channel_snowflake)},
            ),
        }
    return None


async def _get_user_channels(db: Database, snowflake: str):
    channels = await db.fetch_all(
        """SELECT * FROM channel_access WHERE user_snowflake = :user_snowflake""",
        values={"user_snowflake": int(snowflake)},
    )
    return [str(x[0]) for x in channels]


async def _grant_channel_access(
    db: Database, channel_snowflake: str, user_snowflake: str
):
    return await db.execute(
        """INSERT INTO channel_access (user_snowflake, channel_snowflake) VALUES (:user_snowflake, :channel_snowflake) returning channel_snowflake""",
        values={
            "user_snowflake": int(user_snowflake),
            "channel_snowflake": int(channel_snowflake),
        },
    )


async def _has_access_to_channel(
    db: Database, channel_snowflake: int, user_snowflake: int
):
    if channel_snowflake == "0":
        return True
    if (
        await db.execute(
            """SELECT COUNT(*) FROM channel_access WHERE user_snowflake = :user_snowflake AND channel_snowflake = :channel_snowflake""",
            values={
                "user_snowflake": int(user_snowflake),
                "channel_snowflake": int(channel_snowflake),
            },
        )
        > 0
    ):
        return True
    return False


async def _is_owner(db: Database, server_snowflake: str, user_snowflake: str):
    info = await _get_server_info(db, server_snowflake)
    if info is not None:
        if int(info["owner_snowflake"]) == int(user_snowflake):
            return True
        else:
            return "You are not the owner of this server"
    return "Server does not exist"


maxmessages = 100


async def _get_channel_messages(
    db: Database, channel_snowflake: str, limit=None, before=None, _check=True
):
    values = {"channel_snowflake": int(channel_snowflake)}
    limitval = 50
    if limit is not None:
        limitval = int(limit)
        if limitval > maxmessages or limitval < 1:
            return f"Invalid limit, must be between 1-{maxmessages}"
    beforestr = ""
    if before is not None:
        if await _message_exists(db, before):
            beforestr = f"snowflake < :before_snowflake AND "
            values["before_snowflake"] = int(before)
        else:
            return "Before message does not exist"
    messages = await db.fetch_all(
        f"""SELECT (snowflake, author_snowflake, content) FROM messages WHERE {beforestr}channel_snowflake = :channel_snowflake ORDER BY snowflake DESC LIMIT {limitval}""",
        values=values,
    )
    messageslist = [
        {
            "snowflake": str(x[0][0]),
            "author": await _get_user_info(db, str(x[0][1])),
            "content": x[0][2],
        }
        for x in messages
    ]
    # if _check:
    #     if (
    #         len(
    #             await _get_channel_messages(
    #                 db, channel_snowflake, 1, messageslist[-1]["snowflake"], False
    #             )
    #         )
    #         == 0
    #     ):
    #         messageslist.append(None)
    return messageslist


async def _create_message(
    app: quart.app, channel_snowflake: str, author_snowflake: str, content: str
):
    msg = await app.db.fetch_val(
        """INSERT INTO messages (snowflake, channel_snowflake, author_snowflake, content) VALUES (:snowflake, :channel_snowflake, :author_snowflake, :content) RETURNING (snowflake, author_snowflake, content)""",
        values={
            "snowflake": next(app.snowflake_gen),
            "channel_snowflake": int(channel_snowflake),
            "author_snowflake": int(author_snowflake),
            "content": content,
        },
    )
    return {
        "content": msg[2],
        "author": await _get_user_info(app.db, str(msg[1])),
        "snowflake": str(msg[0]),
    }


async def _message_exists(db: Database, message_snowflake: str):
    count = await db.fetch_val(
        """SELECT COUNT(*) FROM messages WHERE snowflake = :snowflake""",
        values={"snowflake": int(message_snowflake)},
    )
    if count > 0:
        return True
    else:
        return False


async def _add_channel_to_server(
    db: Database, server_snowflake: str, channel_snowflake: str
):
    await db.execute(
        f"""INSERT INTO server_channels (server_snowflake, channel_snowflake) VALUES (:server_snowflake, :channel_snowflake)""",
        values={
            "server_snowflake": int(server_snowflake),
            "channel_snowflake": int(channel_snowflake),
        },
    )


async def _get_user_info(db: Database, user_snowflake: str):
    user = await db.fetch_one(
        f"""SELECT (snowflake, username, nickname, picture) FROM users WHERE snowflake = :snowflake""",
        values={"snowflake": int(user_snowflake)},
    )
    if user is not None:
        return {
            "snowflake": str(user[0][0]),
            "username": user[0][1],
            "nickname": user[0][2],
            "picture": user[0][3],
        }
    else:
        return None


async def _add_friend(db: Database, friender: str, friendee: str):
    pass


# async def _is_friend(db: Database, friender: str, friendee: Optional[str]):


async def _get_user_tokens(db: Database, user_snowflake: str):
    tokens = await db.fetch_all(
        """SELECT token FROM tokens WHERE snowflake = :snowflake""",
        values={"snowflake": int(user_snowflake)},
    )
    return [str(x[0]) for x in tokens]


async def _get_channel_users(db: Database, channel_snowflake: str):
    if channel_snowflake == "0":
        users = await db.fetch_all("""SELECT snowflake FROM users""")
    else:
        users = await db.fetch_all(
            """SELECT user_snowflake FROM channel_access WHERE channel_snowflake = :channel_snowflake""",
            values={"channel_snowflake": int(channel_snowflake)},
        )
    return [str(x[0]) for x in users]

async def _update_user_info(db: Database, user_snowflake: str, nickname: Optional[str] = None, picture: Optional[str] = None):
    oldinfo = await _get_user_info(db, user_snowflake)
    values= {"nickname": oldinfo["nickname"], "picture": oldinfo["picture"], "snowflake": int(user_snowflake)}
    if nickname is not None:
        values["nickname"] = nickname
    if picture is not None:
        values["picture"] = picture

    
    userinfo = await db.fetch_val(
        """UPDATE users SET nickname = :nickname, picture = :picture WHERE snowflake = :snowflake RETURNING (snowflake, username, nickname, picture)""", values=values
    )
    return {
        "snowflake": str(userinfo[0]),
        "username": userinfo[1],
        "nickname": userinfo[2],
        "picture": userinfo[3]
    }