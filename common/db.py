import codecs
import hashlib
import math
from typing import Optional
from time import time
from uuid import uuid1
import zlib
import bcrypt
from databases import Database
import common.primitive as Primitive
from snowflake import SnowflakeGenerator

from common.utils import cache


class RIPRAPDatabase:
    def __init__(self, url):
        self.url = url
        self._db = None
        self.snowflake_gen = SnowflakeGenerator(0)
        self.uuid = uuid1

    async def _connect(self):
        self._db = Database(self.url)
        await self._db.connect()

    @cache()
    async def user_get(
        self,
        snowflake: Optional[Primitive.Snowflake] = None,
        username: Optional[str] = None,
        internal: bool = False,
    ) -> Primitive.User:
        if username is not None:
            user = await self._db.fetch_one(
                        """SELECT snowflake FROM users WHERE username = :username""",
                        values={"username": username},
                    )
            if user is None:
                raise Primitive.Error("User does not exist", 404)
            snowflake = await self.snowflake_get(
                user[0]
            )
        if snowflake.resourcetype != Primitive.Type.USER:
            raise Primitive.Error("Snowflake does not represent a user", 400)
        user = await self._db.fetch_one(
            """SELECT (snowflake, username, nickname, picture, passwordhash) FROM users WHERE snowflake = :snowflake""",
            values={"snowflake": snowflake},
        )
        if user is not None:
            user = user[0]
            passwordhash = None
            if internal:
                passwordhash = user[4]
            return Primitive.User(
                snowflake=await self.snowflake_get(user[0]),
                username=user[1],
                nickname=user[2],
                picture=user[3],
                passwordhash=passwordhash,
            )
        else:
            raise Primitive.Error("User does not exist", 404)

    async def user_set(
        self,
        snowflake: Primitive.Snowflake,
        username: str = None,
        nickname: str = None,
        picture: str = None,
        password: str = None,
        oldpassword: str = None,
        delete: bool = False,
    ) -> Primitive.User:
        if snowflake.resourcetype != Primitive.Type.USER:
            raise Primitive.Error("Snowflake does not represent a user", 400)
        user = await self._db.fetch_one(
            """SELECT (snowflake, username, nickname, picture, passwordhash) FROM users WHERE snowflake = :snowflake""",
            values={"snowflake": snowflake},
        )
        if user is not None:
            user: Primitive.User = Primitive.User(
                snowflake=await self.snowflake_get(user[0]),
                username=user[1],
                nickname=user[2],
                picture=user[3],
                passwordhash=user[4],
            )
            if username is None:
                username: str = user.username
            if nickname is None:
                nickname: str = user.nickname
            if picture is None:
                picture: str = user.picture
            if password is None:
                passwordhash: bytes = user.passwordhash
            else:
                if delete:
                    passwordhash = zlib.compress(bcrypt.hashpw(b"", bcrypt.gensalt()))
                else:
                    if oldpassword is None:
                        raise Primitive.Error(
                            "You must provide your old password to change your password",
                            401,
                        )
                    if not bcrypt.checkpw(
                        codecs.encode(user.passwordhash, "utf-8"),
                        zlib.decompress(password),
                    ):
                        raise Primitive.Error("Old password is incorrect", 401)
                    passwordhash: bytes = zlib.compress(
                        bcrypt.hashpw(
                            codecs.encode(password, "utf-8"), bcrypt.gensalt()
                        )
                    )
            newuserdata = await self._db.fetch_val(
                """UPDATE users SET username = :username, nickname = :nickname, picture = :picture, passwordhash = :passwordhash WHERE snowflake = :snowflake RETURNING (snowflake, username, nickname, picture)""",
                values={
                    "snowflake": int(snowflake),
                    "username": username,
                    "nickname": nickname,
                    "picture": picture,
                    "passwordhash": passwordhash,
                },
            )
            return Primitive.User(
                snowflake=await self.snowflake_get(newuserdata[0]),
                username=newuserdata[1],
                nickname=newuserdata[2],
                picture=newuserdata[3],
            )
        else:
            raise Primitive.Error("User does not exist", 404)

    async def user_create(
        self,
        username: str,
        nickname: Optional[str],
        picture: Optional[str],
        password: str,
    ) -> Primitive.User:
        user = await self._db.fetch_val(
            """INSERT INTO users (snowflake, username, nickname, picture, passwordhash) VALUES (:snowflake, :username, :nickname, :picture, :passwordhash) RETURNING (snowflake, username, nickname, picture)""",
            values={
                "snowflake": int(await self.snowflake_create(Primitive.Type.USER)),
                "username": username,
                "nickname": nickname,
                "picture": picture,
                "passwordhash": zlib.compress(
                    bcrypt.hashpw(codecs.encode(password, "utf-8"), bcrypt.gensalt())
                ),
            },
        )
        return Primitive.User(
            snowflake=await self.snowflake_get(user[0]),
            username=user[1],
            nickname=user[2],
            picture=user[3],
        )

    async def user_remove(self, user: Primitive.User):
        await self.user_set(
            snowflake=user.snowflake,
            username=str(next(self.snowflake_gen)),
            nickname="Deleted User",
            picture="http://cdn.deadlyneurotox.in/sXIAsDHeMkONwg1i",
            password="",
            delete=True,
        )
        await self._cleanup_db()

    @cache()
    async def snowflake_get(self, snowflake: str | int) -> Primitive.Snowflake:
        snowflake: int = int(snowflake)
        cacheflake = await self._db.fetch_one(
            """SELECT (snowflake, resourcetype) FROM snowflakes WHERE snowflake = :snowflake""",
            values={"snowflake": snowflake},
        )
        if cacheflake is None:
            cacheflake: Primitive.Snowflake = Primitive.Snowflake(
                snowflake=snowflake, resourcetype=-1
            )
            if (
                await self._db.fetch_val(
                    """SELECT COUNT(*) FROM users WHERE snowflake = :snowflake""",
                    values={"snowflake": snowflake},
                )
            ) > 0:
                cacheflake.resourcetype = Primitive.Type.USER
            if (
                await self._db.fetch_val(
                    """SELECT COUNT(*) FROM servers WHERE snowflake = :snowflake""",
                    values={"snowflake": snowflake},
                )
            ) > 0:
                cacheflake.resourcetype = Primitive.Type.SERVER
            if (
                await self._db.fetch_val(
                    """SELECT COUNT(*) FROM channels WHERE snowflake = :snowflake""",
                    values={"snowflake": snowflake},
                )
            ) > 0:
                cacheflake.resourcetype = Primitive.Type.CHANNEL
            if (
                await self._db.fetch_val(
                    """SELECT COUNT(*) FROM messages WHERE snowflake = :snowflake""",
                    values={"snowflake": snowflake},
                )
            ) > 0:
                cacheflake.resourcetype = Primitive.Type.MESSAGE
            if cacheflake.resourcetype == -1:
                raise Primitive.Error("Snowflake does not exist", 400)
            cacheflake = (
                await self._db.fetch_val(
                    """INSERT INTO snowflakes (snowflake, resourcetype) VALUES (:snowflake, :resourcetype) RETURNING (snowflake, resourcetype)""",
                    values={
                        "snowflake": int(cacheflake.snowflake),
                        "resourcetype": cacheflake.resourcetype,
                    },
                ),
            )
        cacheflake = cacheflake[0]
        return Primitive.Snowflake(snowflake=cacheflake[0], resourcetype=cacheflake[1])

    async def session_get(self, token: str) -> Primitive.Session:
        session = await self._db.fetch_one(
            """SELECT (token, session_name, snowflake) FROM tokens WHERE token = :token""",
            values={"token": token},
        )
        if session is None:
            raise Primitive.Error("Token is invalid", 401)
        session = session[0]
        return Primitive.Session(
            token=session[0],
            session_name=session[1],
            snowflake=await self.snowflake_get(session[2]),
        )

    async def session_create(
        self, snowflake: Primitive.Snowflake, session_name: str
    ) -> Primitive.Session:
        if snowflake.resourcetype != Primitive.Type.USER:
            raise Primitive.Error("Snowflake does not represent a user", 400)
        session = await self._db.fetch_val(
            """INSERT INTO tokens (token, snowflake, session_name) VALUES (:token, :snowflake, :session_name) RETURNING (token, snowflake, session_name)""",
            values={
                "token": hashlib.sha512(
                    codecs.encode(
                        f"{uuid1(16).bytes.hex()} {uuid1(8192).bytes.hex()}",
                        "ascii",
                    )
                ).hexdigest(),
                "snowflake": int(snowflake),
                "session_name": session_name,
            },
        )
        return Primitive.Session(
            token=session[0],
            session_name=session[2],
            snowflake=await self.snowflake_get(session[1]),
        )

    async def session_remove(self, token: str):
        r = await self._db.execute(
            f"""DELETE FROM tokens WHERE token = :token RETURNING session_name""",
            values={"token": token},
        )
        if r is None:
            raise Primitive.Error("Session does not exist", 404)

    async def session_list(
        self, snowflake: Primitive.Snowflake
    ) -> Primitive.List.Sessions:
        if snowflake.resourcetype != Primitive.Type.USER:
            raise Primitive.Error("Snowflake does not represent a user", 400)
        sessions = await self._db.fetch_all(
            """SELECT (token, session_name, snowflake) FROM tokens WHERE snowflake = :snowflake""",
            values={"snowflake": int(snowflake)},
        )
        return Primitive.List.Sessions(
            sessions=[
                Primitive.Session(
                    token=x[0][0],
                    session_name=x[0][1],
                    snowflake=await self.snowflake_get(x[0][2]),
                )
                for x in sessions
            ]
        )

    async def ratelimited_get(
        self, endpoint_id: str, session: Primitive.Session, t: int, maxuses: int
    ):
        await self._db.execute(
            f"""DELETE FROM ratelimit WHERE apiendpoint = :apiendpoint AND timecalled <= :timecalled""",
            values={
                "apiendpoint": endpoint_id,
                "timecalled": math.floor(time()) - t,
            },
        )

        limited = await self._db.fetch_val(
            f"""SELECT COUNT(*) FROM ratelimit WHERE snowflake = :snowflake AND apiendpoint = :apiendpoint""",
            values={"snowflake": int(session.snowflake), "apiendpoint": endpoint_id},
        )

        if limited < maxuses:
            limited = await self._db.fetch_val(
                f"""INSERT INTO ratelimit (snowflake, timecalled, apiendpoint) VALUES (:snowflake, :timecalled, :apiendpoint)""",
                values={
                    "snowflake": int(session.snowflake),
                    "timecalled": math.floor(time()),
                    "apiendpoint": endpoint_id,
                },
            )
            return False
        else:
            timecalled = await self._db.fetch_one(
                f"""SELECT timecalled FROM ratelimit WHERE snowflake = :snowflake AND apiendpoint = :apiendpoint ORDER BY snowflake ASC LIMIT 1""",
                values={
                    "snowflake": int(session.snowflake),
                    "apiendpoint": endpoint_id,
                },
            )
            raise Primitive.Error(
                f"You are being rate limited, you can use this endpoint {maxuses} times every {t} seconds. Your next use is in {t - (math.floor(time()) - timecalled[0])} seconds",
                429,
            )

    @cache()
    async def server_get(self, snowflake: Primitive.Snowflake) -> Primitive.Server:
        if snowflake.resourcetype != Primitive.Type.SERVER:
            raise Primitive.Error("Snowflake does not represent a server", 400)
        server = await self._db.fetch_one(
            """SELECT (name, picture, owner_snowflake) FROM servers WHERE snowflake = :snowflake""",
            values={"snowflake": int(snowflake)},
        )
        if server is None:
            raise Primitive.Error("Snowflake does not exist", 500)
        server = server[0]
        return Primitive.Server(
            name=server[0],
            picture=server[1],
            owner=await self.user_get(await self.snowflake_get(server[2])),
            snowflake=snowflake,
            channels=(await self.channel_list(snowflake)).channels,
            users=(await self.server_list_users(snowflake)).users,
        )

    # async def server_set(
    #     self,
    # ) -> Primitive.Server:
    #     pass

    async def server_create(
        self, owner: Primitive.User, name: str, picture: str
    ) -> Primitive.Server:
        server = await self._db.fetch_val(
            """INSERT INTO servers (name, picture, owner_snowflake, snowflake) VALUES (:name, :picture, :owner_snowflake, :snowflake) RETURNING (name, picture, snowflake)""",
            values={
                "name": name,
                "picture": picture,
                "owner_snowflake": int(owner.snowflake),
                "snowflake": int(await self.snowflake_create(Primitive.Type.SERVER)),
            },
        )
        this_server = await self.server_get(
            snowflake=await self.snowflake_get(server[2])
        )
        await self.server_grant_access(
            server=this_server,
            user=owner,
        )
        return this_server

    async def server_remove(self, snowflake: Primitive.Snowflake):
        if snowflake.resourcetype != Primitive.Type.SERVER:
            raise Primitive.Error("Snowflake does not represent a server", 400)
        await self._db.execute(
            f"""DELETE FROM servers WHERE snowflake = :snowflake""",
            values={"snowflake": int(snowflake)},
        )
        await self._cleanup_db()

    async def server_grant_access(self, server: Primitive.Server, user: Primitive.User):
        await self._db.execute(
            f"""INSERT INTO server_access (server_snowflake, user_snowflake) VALUES (:server_snowflake, :user_snowflake)""",
            values={
                "server_snowflake": int(server.snowflake),
                "user_snowflake": int(user.snowflake),
            },
        )

    async def user_list_servers(self, user: Primitive.User) -> Primitive.List.Servers:
        servers = await self._db.fetch_all(
            """SELECT server_snowflake FROM server_access WHERE user_snowflake = :user_snowflake""",
            values={"user_snowflake": int(user.snowflake)},
        )
        return Primitive.List.Servers(
            servers=[
                await self.server_get(await self.snowflake_get(x[0])) for x in servers
            ]
        )

    async def server_list_users(
        self, server: Primitive.Snowflake
    ) -> Primitive.List.Users:
        if server.resourcetype != Primitive.Type.SERVER:
            raise Primitive.Error("Snowflake does not represent a server", 400)
        users = await self._db.fetch_all(
            """SELECT user_snowflake FROM server_access WHERE server_snowflake = :server_snowflake""",
            values={"server_snowflake": int(server)},
        )

        return Primitive.List.Users(
            users=[await self.user_get(await self.snowflake_get(x[0])) for x in users]
        )

    async def channel_list(
        self, server: Primitive.Snowflake
    ) -> Primitive.List.Channels:
        if server.resourcetype != Primitive.Type.SERVER:
            raise Primitive.Error("Snowflake does not represent a server", 400)
        channels = await self._db.fetch_all(
            """SELECT channel_snowflake FROM server_channels WHERE server_snowflake = :server_snowflake""",
            values={"server_snowflake": int(server.snowflake)},
        )
        return Primitive.List.Channels(
            channels=[
                await self.channel_get(await self.snowflake_get(x[0])) for x in channels
            ]
        )

    @cache()
    async def channel_get(self, snowflake: Primitive.Snowflake) -> Primitive.Channel:
        if snowflake.resourcetype != Primitive.Type.CHANNEL:
            raise Primitive.Error("Snowflake does not represent a channel", 400)
        channel = await self._db.fetch_one(
            """SELECT (name, picture) FROM channels WHERE snowflake = :snowflake""",
            values={"snowflake": int(snowflake)},
        )
        if channel is None:
            raise Primitive.Error("Snowflake does not exist", 500)
        return Primitive.Channel(
            name=channel[0][0],
            picture=channel[0][1],
            snowflake=snowflake,
            message_count=await self._db.fetch_val(
                """SELECT COUNT(*) FROM messages WHERE channel_snowflake = :snowflake""",
                values={"snowflake": int(snowflake)},
            ),
        )

    async def snowflake_create(self, resourcetype: int) -> Primitive.Snowflake:
        snowflake = await self._db.fetch_val(
            """INSERT INTO snowflakes (snowflake, resourcetype) VALUES (:snowflake, :resourcetype) RETURNING snowflake""",
            values={
                "snowflake": next(self.snowflake_gen),
                "resourcetype": resourcetype,
            },
        )
        return await self.snowflake_get(snowflake)

    async def validate_password(self, user: Primitive.User, password: str):
        pwh = await self._db.fetch_val(
            """SELECT passwordhash FROM users WHERE snowflake = :snowflake""",
            values={"snowflake": int(user.snowflake)},
        )
        if not bcrypt.checkpw(password.encode("utf-8"), zlib.decompress(pwh)):
            raise Primitive.Error("Incorrect password", 401)

    async def _cleanup_db(self):
        # remove server channels where server no longer exists or channel no longer exists
        await self._db.execute(
            """DELETE FROM server_channels WHERE server_snowflake NOT IN (SELECT snowflake FROM servers) OR channel_snowflake NOT IN (SELECT snowflake FROM channels)""",
        )
        # remove server access where server no longer exists or user no longer exists
        await self._db.execute(
            """DELETE FROM server_access WHERE server_snowflake NOT IN (SELECT snowflake FROM servers) OR user_snowflake NOT IN (SELECT snowflake FROM users)""",
        )
        # remove channels where server no longer exists
        await self._db.execute(
            """DELETE FROM channels WHERE snowflake NOT IN (SELECT channel_snowflake FROM server_channels)""",
        )
        # remove messages where channel no longer exists
        await self._db.execute(
            """DELETE FROM messages WHERE channel_snowflake NOT IN (SELECT snowflake FROM channels)""",
        )
        # remove tokens where user no longer exists
        await self._db.execute(
            """DELETE FROM tokens WHERE snowflake NOT IN (SELECT snowflake FROM users)""",
        )
        # remove ratelimit where user no longer exists
        await self._db.execute(
            """DELETE FROM ratelimit WHERE snowflake NOT IN (SELECT snowflake FROM users)""",
        )
        # remove snowflakes that no longer exist
        await self._db.execute(
            """DELETE FROM snowflakes WHERE snowflake NOT IN (SELECT snowflake FROM users) AND snowflake NOT IN (SELECT snowflake FROM servers) AND snowflake NOT IN (SELECT snowflake FROM channels) AND snowflake NOT IN (SELECT snowflake FROM messages)""",
        )

    async def channel_create(
        self, server: Primitive.Server, name: str, picture_url: str
    ) -> Primitive.Channel:
        snowflake = await self.snowflake_create(Primitive.Type.CHANNEL)
        await self._db.execute(
            """INSERT INTO channels (snowflake, name, picture) VALUES (:snowflake, :name, :picture)""",
            values={
                "snowflake": int(snowflake),
                "name": name,
                "picture": picture_url,
            },
        )
        await self._db.execute(
            """INSERT INTO server_channels (server_snowflake, channel_snowflake) VALUES (:server_snowflake, :channel_snowflake)""",
            values={
                "server_snowflake": int(server.snowflake),
                "channel_snowflake": int(snowflake),
            },
        )
        return await self.channel_get(snowflake)

    async def user_list_channels(self, user: Primitive.User) -> Primitive.List.Channels:
        channels = await self._db.fetch_all(
            """SELECT channel_snowflake FROM server_channels WHERE server_snowflake IN (SELECT server_snowflake FROM server_access WHERE user_snowflake = :snowflake)""",
            values={"snowflake": int(user.snowflake)},
        )
        return Primitive.List.Channels(
            channels=[
                await self.channel_get(await self.snowflake_get(x[0])) for x in channels
            ]
        )

    async def channel_remove(self, channel: Primitive.Channel):
        # remove channel from server channels and remove channel if channel is no longer in any servers
        await self._db.execute(
            """DELETE FROM server_channels WHERE channel_snowflake = :channel_snowflake""",
            values={"channel_snowflake": int(channel.snowflake)},
        )
        # if channel is no longer in any servers, remove channel
        if (
            await self._db.fetch_val(
                """SELECT COUNT(*) FROM server_channels WHERE channel_snowflake = :channel_snowflake""",
                values={"channel_snowflake": int(channel.snowflake)},
            )
            == 0
        ):
            await self._db.execute(
                """DELETE FROM channels WHERE snowflake = :snowflake""",
                values={"snowflake": int(channel.snowflake)},
            )
        # clean up database
        await self._cleanup_db()

    async def channel_update(
        self,
        channel: Primitive.Channel,
        name: Optional[str],
        picture_url: Optional[str],
    ) -> Primitive.Channel:
        # get server information, set values if anything needs updated, and use this to update the database
        server = await self.server_get(await self.snowflake_get(channel.snowflake))
        values = {"name": server.name, "picture": server.picture}
        if name is not None:
            values["name"] = name
        if picture_url is not None:
            values["picture"] = picture_url
        await self._db.execute(
            """UPDATE channels SET name = :name, picture = :picture WHERE snowflake = :snowflake""",
            values=values,
        )
        return await self.channel_get(channel.snowflake)

    async def message_create(
        self,
        channel: Primitive.Channel,
        content: str,
        author: Primitive.User,
    ):
        snowflake = await self.snowflake_create(Primitive.Type.MESSAGE)
        await self._db.execute(
            """INSERT INTO messages (snowflake, channel_snowflake, content, author_snowflake) VALUES (:snowflake, :channel_snowflake, :content, :author_snowflake)""",
            values={
                "snowflake": int(snowflake),
                "channel_snowflake": int(channel.snowflake),
                "content": content,
                "author_snowflake": int(author.snowflake),
            },
        )
        return await self.message_get(snowflake)

    @cache()
    async def message_get(self, snowflake: Primitive.Snowflake) -> Primitive.Message:
        message = await self._db.fetch_one(
            """SELECT snowflake, channel_snowflake, content, author_snowflake FROM messages WHERE snowflake = :snowflake""",
            values={"snowflake": int(snowflake)},
        )
        channel = await self.channel_get(await self.snowflake_get(message[1]))
        return Primitive.Message(
            snowflake=await self.snowflake_get(message[0]),
            channel=channel,
            content=message[2],
            author=await self.user_get(await self.snowflake_get(message[3])),
        )

    async def channel_list_messages(
        self,
        channel: Primitive.Channel,
        limit: Optional[int],
        before: Optional[int],
    ) -> Primitive.List.Messages:
        if limit is None:
            limit = 25
        else:
            maxlimit = 100
            if limit > maxlimit or limit < 1:
                raise Primitive.Error(
                    f"Limit must be between 1 and {maxlimit} (inclusive)", 400
                )
        if before is None:
            messages = await self._db.fetch_all(
                """SELECT snowflake, content, author_snowflake FROM messages WHERE channel_snowflake = :channel_snowflake ORDER BY snowflake DESC LIMIT :limit""",
                values={"channel_snowflake": int(channel.snowflake), "limit": limit},
            )
        else:
            messages = await self._db.fetch_all(
                """SELECT snowflake, content, author_snowflake FROM messages WHERE channel_snowflake = :channel_snowflake AND snowflake < :before_snowflake ORDER BY snowflake DESC LIMIT :limit""",
                values={
                    "channel_snowflake": int(channel.snowflake),
                    "before_snowflake": before,
                    "limit": limit,
                },
            )
        return Primitive.List.Messages(
            messages=[
                Primitive.Message(
                    snowflake=await self.snowflake_get(x[0]),
                    channel=channel,
                    content=x[1],
                    author=await self.user_get(await self.snowflake_get(x[2])),
                )
                for x in messages
            ]
        )

    async def message_remove(self, message: Primitive.Message):
        await self._db.execute(
            """DELETE FROM messages WHERE snowflake = :snowflake""",
            values={"snowflake": int(message.snowflake)},
        )
        await self._cleanup_db()
