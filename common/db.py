import base64
import codecs
from datetime import datetime
import hashlib
from io import BytesIO
import math
import random
import re
from typing import Optional
from time import time
from uuid import uuid1
import zlib
import bcrypt
from databases import Database
from common.primitive import Channel, Message, Server, Session, User, Error
from snowflake import SnowflakeGenerator
import prisma
from prisma.models import (
    User as UserModel,
    Server as ServerModel,
    Channel as ChannelModel,
    Message as MessageModel,
)
from PIL import Image
import config

# from common.utils import cache


class RIPRAPDatabase:
    def __init__(self, url):
        self.url = url
        self._db = None
        self.snowflake_gen = SnowflakeGenerator(0)
        self.uuid = uuid1

    async def _connect(self):
        self._db = prisma.Client(log_queries=False)
        # self._db.server = self.url
        await self._db.connect()

    # @cache()
    # async def _userModelToUser(
    #     self,
    #     user: UserModel,
    #     constraintUser: UserModel = None,
    #     constraintLayer: int = 0,
    # ) -> User:
    #     if constraintLayer == 2:
    #         return User(
    #             snowflake=user.snowflake,
    #             name=user.name,
    #             picture=user.picture.decode_str(),
    #         )

    #     if constraintLayer == 1:
    #         if constraintUser is None:
    #             return User(
    #                 snowflake=user.snowflake,
    #                 name=user.name,
    #                 picture=self._b64obj_to_string(user.picture),
    #             )
    #         else:
    #             friends = []
    #             for friend in user.friends or []:
    #                 if friend.snowflake == constraintUser.snowflake:
    #                     friends.append(
    #                         await self._userModelToUser(friend, constraintLayer=2)
    #                     )
    #             servers = []
    #             for server in user.inServers or []:
    #                 servermembers = [
    #                     x.user.snowflake for x in server.server.members or []
    #                 ]
    #                 if constraintUser.snowflake in servermembers:
    #                     servers.append(await self._serverModelToServer(server.server))
    #             return User(
    #                 snowflake=user.snowflake,
    #                 name=user.name,
    #                 picture=self._b64obj_to_string(user.picture),
    #                 friends=friends,
    #                 servers=servers,
    #             )

    #     if constraintLayer == 0:
    #         servers = []
    #         for server in user.inServers or []:
    #             servers.append(await self._serverModelToServer(server.server))
    #         return User(
    #             snowflake=user.snowflake,
    #             name=user.name,
    #             picture=self._b64obj_to_string(user.picture),
    #             friends=[
    #                 await self._userModelToUser(x, user, constraintLayer=1)
    #                 for x in user.friends or []
    #             ],
    #         )

    # async def _serverModelToServer(self, server: ServerModel) -> Server:
    #     return Server(
    #         snowflake=server.snowflake,
    #         name=server.name,
    #         picture=self._b64obj_to_string(server.picture),
    #         channels=[await self._channelModelToChannel(x) for x in server.channels],
    #         users=[
    #             await self._userModelToUser(x, constraintLayer=2)
    #             for x in server.members
    #         ],
    #     )

    # async def _channelModelToChannel(self, channel: ChannelModel) -> Channel:
    #     return Channel(
    #         snowflake=channel.snowflake,
    #         name=channel.name,
    #         picture=self._b64obj_to_string(channel.picture),
    #         message_count=channel.messages.count(),
    #     )

    # def _b64obj_to_string(self, b64obj: prisma.Base64) -> str:ToUser
    #     return base64.b64encode(b64obj.decode()).decode("utf-8")

    async def user_get(
        self,
        *,
        snowflake: Optional[int | str] = None,
        email: Optional[str] = None,
        level: int = 1,
    ) -> User:
        if email is not None:
            user = await self._db.user.find_unique(
                where={"email": email},
                include={
                    "friends": True,
                    "inServers": {
                        "include": {
                            "server": {
                                "include": {
                                    "owner": True,
                                }
                            }
                        }
                    },
                },
            )
        elif snowflake is not None:
            snowflake = int(snowflake)
            user = await self._db.user.find_unique(
                where={"snowflake": snowflake},
                include={
                    "friends": True,
                    "inServers": {
                        "include": {
                            "server": {
                                "include": {
                                    "owner": True,
                                }
                            }
                        }
                    },
                },
            )
        else:
            raise Error("Either snowflake or email must be provided", 400)
        if user is None:
            raise Error("User not found", 404)
        return User.from_prisma(user, level)

    async def user_set(
        self,
        *,
        snowflake: Optional[int | str] = None,
        name: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        newpassword: Optional[str] = None,
        picture: Optional[bytes] = None,
        delete: bool = False,
    ) -> User:
        if snowflake is not None:
            snowflake = int(snowflake)
            user = await self._db.user.find_unique(where={"snowflake": snowflake})
            if user is None:
                raise Error("User not found", 404)
            if delete:
                if password is None:
                    raise Error("Password is required to delete account", 401)
                if not bcrypt.checkpw(
                    codecs.encode(password, "utf-8"), user.password.decode()
                ):
                    raise Error("Password incorrect", 401)
                newuserdata = {
                    "snowflake": user.snowflake,
                    "name": f"DeletedUser{self._generate_token()}",
                    "email": self._generate_token(),
                    "picture": prisma.Base64.encode(
                        self._get_random_default_image(deleted=True)
                    ),
                    "password": prisma.Base64.encode(b""),
                }
                await self._db.user.delete(where={"snowflake": snowflake})
                deleteduser = await self._db.user.create(data=newuserdata)
                return User.from_prisma(deleteduser, 1)
            else:
                verified = [False, False]
                if email is not None or newpassword is not None:
                    if password is None:
                        raise Error(
                            "Password is required to update protected fields", 401
                        )
                    if not bcrypt.checkpw(
                        codecs.encode(password, "utf-8"), user.password.decode()
                    ):
                        raise Error("Password incorrect", 401)
                    verified = [email is not None, newpassword is not None]
                newuserinfo = {
                    "name": name or user.name,
                    "email": self._verify_email(email) if verified[0] else user.email,
                    "password": prisma.Base64.encode(
                        bcrypt.hashpw(
                            codecs.encode(newpassword, "utf-8"),
                            bcrypt.gensalt(),
                        )
                    )
                    if verified[1]
                    else user.password,
                    "picture": prisma.Base64.encode(
                        self._format_picture(picture) or user.picture.decode()
                    ),
                }
            return User.from_prisma(
                await self._db.user.update(
                    data=newuserinfo, where={"snowflake": snowflake}
                )
            )
        else:
            if delete:
                raise Error("Cannot delete user without Snowflake", 400)
            newuserinfo = {
                "name": name or self._inline_raise_error("Name is required", 400),
                "email": self._verify_email(
                    email or self._inline_raise_error("Email is required", 400)
                ),
                "password": prisma.Base64.encode(
                    bcrypt.hashpw(
                        codecs.encode(
                            password
                            or self._inline_raise_error("Password is required", 400),
                            "utf-8",
                        ),
                        bcrypt.gensalt(),
                    )
                ),
                "picture": prisma.Base64.encode(self._get_random_default_image()),
                "snowflake": next(self.snowflake_gen),
            }
            return User.from_prisma(
                await self._db.user.create(data=newuserinfo),
                nocache=True,
            )

    def _verify_email(self, email) -> str:
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise Error("Email is not valid", 400)
        return email

    async def session_get(
        self, *, token: str, listall: bool = False
    ) -> Session | list[Session]:
        session = await self._db.session.find_unique(
            where={"token": token},
            include={
                "user": True,
            },
        )
        if session is None:
            raise Error("Token is invalid", 401)
        if not listall:
            return Session.from_prisma(session)
        else:
            return [
                Session.from_prisma(x)
                for x in await self._db.session.find_many(
                    where={"userSnowflake": session.userSnowflake},
                    include={
                        "user": True,
                    },
                )
            ]

    async def session_set(
        self,
        *,
        email: Optional[str] = None,
        session_name: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Session:
        if token is None:
            user = await self._db.user.find_unique(where={"email": email})
            if user is None:
                raise Error("User not found", 404)
            if not bcrypt.checkpw(
                codecs.encode(password, "utf-8"), user.password.decode()
            ):
                raise Error("Password incorrect", 401)
            if not user.emailVerified:
                # raise Error("Email not verified", 401)
                pass

            session = await self._db.session.create(
                data={
                    # "userSnowflake": user.snowflake,
                    "session_name": session_name
                    or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "token": self._generate_token(),
                    "user": {"connect": {"snowflake": user.snowflake}},
                },
                include={
                    "user": True,
                },
            )
            return Session.from_prisma(
                session,
                nocache=True,
            )
        else:
            session = await self._db.session.delete(
                where={"token": token},
                include={
                    "user": True,
                },
            )
            if session is None:
                raise Error("Session not found", 401)
            return Session.from_prisma(
                session,
                nocache=True,
            )

    def _inline_raise_error(self, message: str, code: int) -> None:
        raise Error(message, code)

    def _get_random_default_image(self, deleted=False) -> bytes:
        im = Image.open(BytesIO(base64.b64decode(config.DEFAULT_USER_IMAGE_BASE64)))
        bg = Image.new("RGBA", (im.width, im.height), self._random_color())
        bg.paste(im, (0, 0), im)
        if deleted:
            dl = Image.open(
                BytesIO(base64.b64decode(config.DELETED_OVERLAY_BASE64))
            ).convert("RGBA")
            bg.paste(dl, (0, 0), dl)
        bytesout = BytesIO()
        bg.save(bytesout, format="PNG")
        return bytesout.getvalue()

    def _generate_token(self) -> str:
        return hashlib.sha512(
            codecs.encode(
                f"{uuid1(16).bytes.hex()} {uuid1(8192).bytes.hex()}",
                "ascii",
            )
        ).hexdigest()

    def _random_color(self, amount=(255 * 3) / 2):
        rgb = [0, 0, 0]
        for i in range(3):
            rgb[i] = random.randint(0, 255)
        total = sum(rgb)
        for i in range(3):
            rgb[i] = int((rgb[i] / total) * amount)
        return tuple(rgb + [255])

    async def server_get(self, *, snowflake: int | str, user: User) -> Server:
        snowflake = int(snowflake)
        server = await self._db.server.find_many(
            where={
                "snowflake": snowflake,
                "members": {"some": {"userSnowflake": user.snowflake}},
            },
            include={
                "owner": True,
                "members": {
                    "include": {"user": True},
                },
                "channels": True,
            },
        )
        if len(server) == 0:
            raise Error("Server not found", 404)
        return Server.from_prisma(server[0])

    async def server_set(
        self,
        *,
        user: User,
        snowflake: Optional[int | str] = None,
        name: Optional[str] = None,
        picture: Optional[bytes] = None,
        delete: bool = False,
    ) -> Optional[Server]:
        if snowflake is not None:
            snowflake = int(snowflake)
            server = await self._db.server.find_unique(
                where={"snowflake": snowflake},
                include={
                    "owner": True,
                    "members": {
                        "include": {"user": True},
                    },
                },
            )
            if server.owner.snowflake != int(user.snowflake):
                raise Error("You are not the owner of this server", 401)
            if server is None:
                raise Error("Server not found", 404)
            if delete:
                await self._db.server.delete(where={"snowflake": snowflake})
                return None
            newdata = {
                "name": name or server.name,
                "picture": self._format_picture(picture) or server.picture,
            }
            await self._db.server.update(where={"snowflake": snowflake}, data=newdata)
            return Server.from_prisma(
                await self._db.server.find_unique(
                    where={"snowflake": snowflake},
                    include={
                        "owner": True,
                        "members": {
                            "include": {"user": True},
                        },
                    },
                ),
                nocache=True,
            )
        else:
            snowflake = int(user.snowflake)
            server = await self._db.server.create(
                data={
                    "name": name or self._inline_raise_error("Name is required", 400),
                    "picture": prisma.Base64.encode(
                        self._format_picture(picture)
                        or self._get_server_default_image()
                    ),
                    "snowflake": next(self.snowflake_gen),
                    "owner": {"connect": {"snowflake": snowflake}},
                    "ownerSnowflake": snowflake,
                },
            )
            await self._db.serverusersrelation.create(
                data={
                    "server": {"connect": {"snowflake": server.snowflake}},
                    "user": {"connect": {"snowflake": user.snowflake}},
                }
            )
            server = await self._db.server.find_unique(
                where={"snowflake": server.snowflake},
                include={
                    "members": {
                        "include": {
                            "user": True,
                        },
                    },
                    "owner": True,
                },
            )
            return Server.from_prisma(
                server,
                nocache=True,
            )

    async def channel_get(self, *, channel_snowflake: int | str, user: User) -> Channel:
        # get channel where snowflake = channel_snowflake and user is in channel members
        channel_snowflake = int(channel_snowflake)
        user_snowflake = int(user.snowflake)
        channel = await self._db.channel.find_many(
            where={
                "snowflake": channel_snowflake,
                "server": {"members": {"some": {"userSnowflake": user_snowflake}}},
            },
            include={
                "messages": True,
            },
        )
        if len(channel) == 0:
            raise Error("Channel not found", 404)
        return Channel.from_prisma(channel[0])

    async def channel_set(
        self,
        *,
        user: User,
        snowflake: Optional[int | str] = None,
        name: Optional[str] = None,
        picture: Optional[bytes] = None,
        server: Optional[Server] = None,
        delete: bool = False,
    ) -> Optional[Channel]:

        user_snowflake = int(user.snowflake)
        if snowflake is not None:
            snowflake = int(snowflake)
            channel = await self._db.channel.find_many(
                where={
                    "snowflake": snowflake,
                    "server": {"owner": {"snowflake": user_snowflake}},
                },
                include={
                    "messages": True,
                },
            )
            if len(channel) == 0:
                raise Error(
                    "Channel not found or you are not the owner of this server", 404
                )
            if delete:
                await self._db.channel.delete(where={"snowflake": snowflake})
                return None
            newdata = {
                "name": name or channel[0].name,
                "picture": self._format_picture(picture) or channel[0].picture,
            }
            await self._db.channel.update(where={"snowflake": snowflake}, data=newdata)
            return Channel.from_prisma(
                await self._db.channel.find_unique(
                    where={"snowflake": snowflake},
                    include={
                        "server": {
                            "include": {
                                "members": {
                                    "include": {"user": True},
                                },
                                "owner": True,
                            },
                        },
                        "messages": True,
                    },
                ),
                nocache=True,
            )
        else:
            if server is None:
                raise Error("Server is required", 400)
            if server.owner.snowflake != user.snowflake:
                raise Error("You are not the owner of this server", 401)
            server_snowflake = int(server.snowflake)
            channel = await self._db.channel.create(
                data={
                    "name": name or self._inline_raise_error("Name is required", 400),
                    "picture": prisma.Base64.encode(
                        self._format_picture(picture)
                        or self._get_channel_default_image()
                    ),
                    "snowflake": next(self.snowflake_gen),
                    "server": {"connect": {"snowflake": server_snowflake}},
                },
                include={
                    "messages": True,
                },
            )
            return Channel.from_prisma(
                await self._db.channel.find_unique(
                    where={"snowflake": channel.snowflake},
                    include={
                        "server": {
                            "include": {
                                "members": {
                                    "include": {"user": True},
                                },
                                "owner": True,
                            },
                        },
                        "messages": True,
                    },
                ),
                nocache=True,
            )

    def _get_server_default_image(self) -> bytes:
        im = Image.open(BytesIO(base64.b64decode(config.DEFAULT_SERVER_IMAGE_BASE64)))
        bg = Image.new("RGBA", (im.width, im.height), self._random_color())
        bg.paste(im, (0, 0), im)
        bytesout = BytesIO()
        bg.save(bytesout, format="PNG")
        return bytesout.getvalue()

    def _get_channel_default_image(self) -> bytes:
        im = Image.open(BytesIO(base64.b64decode(config.DEFAULT_CHANNEL_IMAGE_BASE64)))
        bg = Image.new("RGBA", (im.width, im.height), self._random_color())
        bg.paste(im, (0, 0), im)
        bytesout = BytesIO()
        bg.save(bytesout, format="PNG")
        return bytesout.getvalue()

    async def message_get(
        self,
        *,
        channel: Channel,
        limit: int = 10,
        before: Optional[int | str] = None,
    ) -> list[Message]:
        messages = await self._db.message.find_many(
            where={
                "channel": {
                    "snowflake": int(channel.snowflake),
                },
            }.update({} if before is None else {"snowflake": {"lt": int(before)}}),
            order={"snowflake": "desc"},
            take=limit,
            include={
                "author": True,
                "channel": True,
            },
        )
        if messages is None:
            raise Error("Channel not found", 404)
        return [Message.from_prisma(x) for x in messages]

    async def message_set(
        self,
        *,
        user: User,
        channel: Channel,
        snowflake: Optional[int | str] = None,
        content: Optional[str] = None,
        delete: bool = False,
    ) -> Optional[Message]:
        user_snowflake = int(user.snowflake)
        userstuff = await self._db.serverusersrelation.find_many(
            where={"user": {"snowflake": user_snowflake}},
            include={"server": {"include": {"channels": True, "owner": True}}},
        )
        owner = False
        found = False
        for server in userstuff:
            if int(channel.snowflake) in [x.snowflake for x in server.server.channels]:
                found = True
                if found:
                    owner = server.server.owner.snowflake == user_snowflake
        if not found:
            raise Error("You are not in this channel", 401)
        if snowflake is not None:
            snowflake = int(snowflake)
            message = await self._db.message.find_many(
                where={
                    "snowflake": snowflake,
                },
                include={
                    "author": True,
                },
            )
            if len(message) == 0:
                raise Error("Message not found", 404)
            if (message[0].author.snowflake == user_snowflake or owner) and delete:
                await self._db.message.delete(where={"snowflake": snowflake})
                return None

            if message[0].author.snowflake != user_snowflake:
                raise Error("You are not the author of this message", 401)

            newdata = {"content": content or message[0].content}
            await self._db.message.update(where={"snowflake": snowflake}, data=newdata)
            return Message.from_prisma(
                await self._db.message.find_unique(
                    where={"snowflake": snowflake},
                    include={
                        "author": True,
                        "channel": True,
                    },
                ),
                nocache=True,
            )
        else:
            message = await self._db.message.create(
                data={
                    "content": content
                    or self._inline_raise_error("Content is required", 400),
                    "snowflake": next(self.snowflake_gen),
                    "channel": {"connect": {"snowflake": int(channel.snowflake)}},
                    "author": {"connect": {"snowflake": user_snowflake}},
                },
            )
            return Message.from_prisma(
                await self._db.message.find_unique(
                    where={"snowflake": message.snowflake},
                    include={
                        "author": True,
                        "channel": True,
                    },
                )
            )

    def _format_picture(self, picture) -> Optional[bytes]:
        if picture is None:
            return None
        try:
            im = Image.open(BytesIO(base64.b64decode(picture)))
            im = im.resize((100, 100))
            bytesout = BytesIO()
            im.save(bytesout, format="PNG")
            return bytesout.getvalue()
        except:
            return None

    async def member_set(
        self, *, owner: Optional[User] = None, server: Server, member: Optional[str]
    ):
        if member is not None:
            if owner is None:
                raise Error("User is required", 400)
            if server.owner.snowflake != owner.snowflake:
                raise Error("You are not the owner of this server", 401)
            return await self._db.server.update(
                where={"snowflake": int(server.snowflake)},
                data={"members": {"disconnect": {"snowflake": int(member)}}},
            )
        else:
            if member is None:
                raise Error("Member is required", 400)
            return await self._db.server.update(
                where={"snowflake": int(server.snowflake)},
                data={"members": {"connect": {"snowflake": int(member)}}},
            )

    # async def ratelimited_get(
    #     self, endpoint_id: str, session: Primitive.Session, t: int, maxuses: int
    # ):
    #     await self._db.execute(
    #         f"""DELETE FROM ratelimit WHERE apiendpoint = :apiendpoint AND timecalled <= :timecalled""",
    #         values={
    #             "apiendpoint": endpoint_id,
    #             "timecalled": math.floor(time()) - t,
    #         },
    #     )

    #     limited = await self._db.fetch_val(
    #         f"""SELECT COUNT(*) FROM ratelimit WHERE snowflake = :snowflake AND apiendpoint = :apiendpoint""",
    #         values={"snowflake": int(session.snowflake), "apiendpoint": endpoint_id},
    #     )

    #     if limited < maxuses:
    #         limited = await self._db.fetch_val(
    #             f"""INSERT INTO ratelimit (snowflake, timecalled, apiendpoint) VALUES (:snowflake, :timecalled, :apiendpoint)""",
    #             values={
    #                 "snowflake": int(session.snowflake),
    #                 "timecalled": math.floor(time()),
    #                 "apiendpoint": endpoint_id,
    #             },
    #         )
    #         return False
    #     else:
    #         timecalled = await self._db.fetch_one(
    #             f"""SELECT timecalled FROM ratelimit WHERE snowflake = :snowflake AND apiendpoint = :apiendpoint ORDER BY snowflake ASC LIMIT 1""",
    #             values={
    #                 "snowflake": int(session.snowflake),
    #                 "apiendpoint": endpoint_id,
    #             },
    #         )
    #         raise Primitive.Error(
    #             f"You are being rate limited, you can use this endpoint {maxuses} times every {t} seconds. Your next use is in {t - (math.floor(time()) - timecalled[0])} seconds",
    #             429,
    #         )

    # @cache()
    # async def server_get(self, snowflake: Primitive.Snowflake) -> Primitive.Server:
    #     if snowflake.resourcetype != Primitive.Type.SERVER:
    #         raise Primitive.Error("Snowflake does not represent a server", 400)
    #     server = await self._db.fetch_one(
    #         """SELECT (name, picture, owner_snowflake) FROM servers WHERE snowflake = :snowflake""",
    #         values={"snowflake": int(snowflake)},
    #     )
    #     if server is None:
    #         raise Primitive.Error("Snowflake does not exist", 500)
    #     server = server[0]
    #     return Primitive.Server(
    #         name=server[0],
    #         picture=server[1],
    #         owner=await self.user_get(await self.snowflake_get(server[2])),
    #         snowflake=snowflake,
    #         channels=(await self.channel_list(snowflake)).channels,
    #         users=(await self.server_list_users(snowflake)).users,
    #     )

    # # async def server_set(
    # #     self,
    # # ) -> Primitive.Server:
    # #     pass

    # async def server_create(
    #     self, owner: Primitive.User, name: str, picture: str
    # ) -> Primitive.Server:
    #     server = await self._db.fetch_val(
    #         """INSERT INTO servers (name, picture, owner_snowflake, snowflake) VALUES (:name, :picture, :owner_snowflake, :snowflake) RETURNING (name, picture, snowflake)""",
    #         values={
    #             "name": name,
    #             "picture": picture,
    #             "owner_snowflake": int(owner.snowflake),
    #             "snowflake": int(await self.snowflake_create(Primitive.Type.SERVER)),
    #         },
    #     )
    #     this_server = await self.server_get(
    #         snowflake=await self.snowflake_get(server[2])
    #     )
    #     await self.server_grant_access(
    #         server=this_server,
    #         user=owner,
    #     )
    #     return this_server

    # async def server_remove(self, snowflake: Primitive.Snowflake):
    #     if snowflake.resourcetype != Primitive.Type.SERVER:
    #         raise Primitive.Error("Snowflake does not represent a server", 400)
    #     await self._db.execute(
    #         f"""DELETE FROM servers WHERE snowflake = :snowflake""",
    #         values={"snowflake": int(snowflake)},
    #     )
    #     await self._cleanup_db()

    # async def server_grant_access(self, server: Primitive.Server, user: Primitive.User):
    #     await self._db.execute(
    #         f"""INSERT INTO server_access (server_snowflake, user_snowflake) VALUES (:server_snowflake, :user_snowflake)""",
    #         values={
    #             "server_snowflake": int(server.snowflake),
    #             "user_snowflake": int(user.snowflake),
    #         },
    #     )

    # async def user_list_servers(self, user: Primitive.User) -> Primitive.List.Servers:
    #     servers = await self._db.fetch_all(
    #         """SELECT server_snowflake FROM server_access WHERE user_snowflake = :user_snowflake""",
    #         values={"user_snowflake": int(user.snowflake)},
    #     )
    #     return Primitive.List.Servers(
    #         servers=[
    #             await self.server_get(await self.snowflake_get(x[0])) for x in servers
    #         ]
    #     )

    # async def server_list_users(
    #     self, server: Primitive.Snowflake
    # ) -> Primitive.List.Users:
    #     if server.resourcetype != Primitive.Type.SERVER:
    #         raise Primitive.Error("Snowflake does not represent a server", 400)
    #     users = await self._db.fetch_all(
    #         """SELECT user_snowflake FROM server_access WHERE server_snowflake = :server_snowflake""",
    #         values={"server_snowflake": int(server)},
    #     )

    #     return Primitive.List.Users(
    #         users=[await self.user_get(await self.snowflake_get(x[0])) for x in users]
    #     )

    # async def channel_list(
    #     self, server: Primitive.Snowflake
    # ) -> Primitive.List.Channels:
    #     if server.resourcetype != Primitive.Type.SERVER:
    #         raise Primitive.Error("Snowflake does not represent a server", 400)
    #     channels = await self._db.fetch_all(
    #         """SELECT channel_snowflake FROM server_channels WHERE server_snowflake = :server_snowflake""",
    #         values={"server_snowflake": int(server.snowflake)},
    #     )
    #     return Primitive.List.Channels(
    #         channels=[
    #             await self.channel_get(await self.snowflake_get(x[0])) for x in channels
    #         ]
    #     )

    # @cache()
    # async def channel_get(self, snowflake: Primitive.Snowflake) -> Primitive.Channel:
    #     if snowflake.resourcetype != Primitive.Type.CHANNEL:
    #         raise Primitive.Error("Snowflake does not represent a channel", 400)
    #     channel = await self._db.fetch_one(
    #         """SELECT (name, picture) FROM channels WHERE snowflake = :snowflake""",
    #         values={"snowflake": int(snowflake)},
    #     )
    #     if channel is None:
    #         raise Primitive.Error("Snowflake does not exist", 500)
    #     return Primitive.Channel(
    #         name=channel[0][0],
    #         picture=channel[0][1],
    #         snowflake=snowflake,
    #         message_count=await self._db.fetch_val(
    #             """SELECT COUNT(*) FROM messages WHERE channel_snowflake = :snowflake""",
    #             values={"snowflake": int(snowflake)},
    #         ),
    #     )

    # async def snowflake_create(self, resourcetype: int) -> Primitive.Snowflake:
    #     snowflake = await self._db.fetch_val(
    #         """INSERT INTO snowflakes (snowflake, resourcetype) VALUES (:snowflake, :resourcetype) RETURNING snowflake""",
    #         values={
    #             "snowflake": next(self.snowflake_gen),
    #             "resourcetype": resourcetype,
    #         },
    #     )
    #     return await self.snowflake_get(snowflake)

    # async def validate_password(self, user: Primitive.User, password: str):
    #     pwh = await self._db.fetch_val(
    #         """SELECT passwordhash FROM users WHERE snowflake = :snowflake""",
    #         values={"snowflake": int(user.snowflake)},
    #     )
    #     if not bcrypt.checkpw(password.encode("utf-8"), zlib.decompress(pwh)):
    #         raise Primitive.Error("Incorrect password", 401)

    # async def _cleanup_db(self):
    #     # remove server channels where server no longer exists or channel no longer exists
    #     await self._db.execute(
    #         """DELETE FROM server_channels WHERE server_snowflake NOT IN (SELECT snowflake FROM servers) OR channel_snowflake NOT IN (SELECT snowflake FROM channels)""",
    #     )
    #     # remove server access where server no longer exists or user no longer exists
    #     await self._db.execute(
    #         """DELETE FROM server_access WHERE server_snowflake NOT IN (SELECT snowflake FROM servers) OR user_snowflake NOT IN (SELECT snowflake FROM users)""",
    #     )
    #     # remove channels where server no longer exists
    #     await self._db.execute(
    #         """DELETE FROM channels WHERE snowflake NOT IN (SELECT channel_snowflake FROM server_channels)""",
    #     )
    #     # remove messages where channel no longer exists
    #     await self._db.execute(
    #         """DELETE FROM messages WHERE channel_snowflake NOT IN (SELECT snowflake FROM channels)""",
    #     )
    #     # remove tokens where user no longer exists
    #     await self._db.execute(
    #         """DELETE FROM tokens WHERE snowflake NOT IN (SELECT snowflake FROM users)""",
    #     )
    #     # remove ratelimit where user no longer exists
    #     await self._db.execute(
    #         """DELETE FROM ratelimit WHERE snowflake NOT IN (SELECT snowflake FROM users)""",
    #     )
    #     # remove snowflakes that no longer exist
    #     await self._db.execute(
    #         """DELETE FROM snowflakes WHERE snowflake NOT IN (SELECT snowflake FROM users) AND snowflake NOT IN (SELECT snowflake FROM servers) AND snowflake NOT IN (SELECT snowflake FROM channels) AND snowflake NOT IN (SELECT snowflake FROM messages)""",
    #     )

    # async def channel_create(
    #     self, server: Primitive.Server, name: str, picture_url: str
    # ) -> Primitive.Channel:
    #     snowflake = await self.snowflake_create(Primitive.Type.CHANNEL)
    #     await self._db.execute(
    #         """INSERT INTO channels (snowflake, name, picture) VALUES (:snowflake, :name, :picture)""",
    #         values={
    #             "snowflake": int(snowflake),
    #             "name": name,
    #             "picture": picture_url,
    #         },
    #     )
    #     await self._db.execute(
    #         """INSERT INTO server_channels (server_snowflake, channel_snowflake) VALUES (:server_snowflake, :channel_snowflake)""",
    #         values={
    #             "server_snowflake": int(server.snowflake),
    #             "channel_snowflake": int(snowflake),
    #         },
    #     )
    #     return await self.channel_get(snowflake)

    # async def user_list_channels(self, user: Primitive.User) -> Primitive.List.Channels:
    #     channels = await self._db.fetch_all(
    #         """SELECT channel_snowflake FROM server_channels WHERE server_snowflake IN (SELECT server_snowflake FROM server_access WHERE user_snowflake = :snowflake)""",
    #         values={"snowflake": int(user.snowflake)},
    #     )
    #     return Primitive.List.Channels(
    #         channels=[
    #             await self.channel_get(await self.snowflake_get(x[0])) for x in channels
    #         ]
    #     )

    # async def channel_remove(self, channel: Primitive.Channel):
    #     # remove channel from server channels and remove channel if channel is no longer in any servers
    #     await self._db.execute(
    #         """DELETE FROM server_channels WHERE channel_snowflake = :channel_snowflake""",
    #         values={"channel_snowflake": int(channel.snowflake)},
    #     )
    #     # if channel is no longer in any servers, remove channel
    #     if (
    #         await self._db.fetch_val(
    #             """SELECT COUNT(*) FROM server_channels WHERE channel_snowflake = :channel_snowflake""",
    #             values={"channel_snowflake": int(channel.snowflake)},
    #         )
    #         == 0
    #     ):
    #         await self._db.execute(
    #             """DELETE FROM channels WHERE snowflake = :snowflake""",
    #             values={"snowflake": int(channel.snowflake)},
    #         )
    #     # clean up database
    #     await self._cleanup_db()

    # async def channel_update(
    #     self,
    #     channel: Primitive.Channel,
    #     name: Optional[str],
    #     picture_url: Optional[str],
    # ) -> Primitive.Channel:
    #     # get server information, set values if anything needs updated, and use this to update the database
    #     server = await self.server_get(await self.snowflake_get(channel.snowflake))
    #     values = {"name": server.name, "picture": server.picture}
    #     if name is not None:
    #         values["name"] = name
    #     if picture_url is not None:
    #         values["picture"] = picture_url
    #     await self._db.execute(
    #         """UPDATE channels SET name = :name, picture = :picture WHERE snowflake = :snowflake""",
    #         values=values,
    #     )
    #     return await self.channel_get(channel.snowflake)

    # async def message_create(
    #     self,
    #     channel: Primitive.Channel,
    #     content: str,
    #     author: Primitive.User,
    # ):
    #     snowflake = await self.snowflake_create(Primitive.Type.MESSAGE)
    #     await self._db.execute(
    #         """INSERT INTO messages (snowflake, channel_snowflake, content, author_snowflake) VALUES (:snowflake, :channel_snowflake, :content, :author_snowflake)""",
    #         values={
    #             "snowflake": int(snowflake),
    #             "channel_snowflake": int(channel.snowflake),
    #             "content": content,
    #             "author_snowflake": int(author.snowflake),
    #         },
    #     )
    #     return await self.message_get(snowflake)

    # @cache()
    # async def message_get(self, snowflake: Primitive.Snowflake) -> Primitive.Message:
    #     message = await self._db.fetch_one(
    #         """SELECT snowflake, channel_snowflake, content, author_snowflake FROM messages WHERE snowflake = :snowflake""",
    #         values={"snowflake": int(snowflake)},
    #     )
    #     channel = await self.channel_get(await self.snowflake_get(message[1]))
    #     return Primitive.Message(
    #         snowflake=await self.snowflake_get(message[0]),
    #         channel=channel,
    #         content=message[2],
    #         author=await self.user_get(await self.snowflake_get(message[3])),
    #     )

    # async def channel_list_messages(
    #     self,
    #     channel: Primitive.Channel,
    #     limit: Optional[int],
    #     before: Optional[int],
    # ) -> Primitive.List.Messages:
    #     if limit is None:
    #         limit = 25
    #     else:
    #         maxlimit = 100
    #         if limit > maxlimit or limit < 1:
    #             raise Primitive.Error(
    #                 f"Limit must be between 1 and {maxlimit} (inclusive)", 400
    #             )
    #     if before is None:
    #         messages = await self._db.fetch_all(
    #             """SELECT snowflake, content, author_snowflake FROM messages WHERE channel_snowflake = :channel_snowflake ORDER BY snowflake DESC LIMIT :limit""",
    #             values={"channel_snowflake": int(channel.snowflake), "limit": limit},
    #         )
    #     else:
    #         messages = await self._db.fetch_all(
    #             """SELECT snowflake, content, author_snowflake FROM messages WHERE channel_snowflake = :channel_snowflake AND snowflake < :before_snowflake ORDER BY snowflake DESC LIMIT :limit""",
    #             values={
    #                 "channel_snowflake": int(channel.snowflake),
    #                 "before_snowflake": before,
    #                 "limit": limit,
    #             },
    #         )
    #     return Primitive.List.Messages(
    #         messages=[
    #             Primitive.Message(
    #                 snowflake=await self.snowflake_get(x[0]),
    #                 channel=channel,
    #                 content=x[1],
    #                 author=await self.user_get(await self.snowflake_get(x[2])),
    #             )
    #             for x in messages
    #         ]
    #     )

    # async def message_remove(self, message: Primitive.Message):
    #     await self._db.execute(
    #         """DELETE FROM messages WHERE snowflake = :snowflake""",
    #         values={"snowflake": int(message.snowflake)},
    #     )
    #     await self._cleanup_db()
