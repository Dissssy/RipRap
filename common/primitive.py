import base64
from prisma import Prisma, Base64, models
from pydantic import BaseModel
from typing import Optional

from common.utils import sync_cache


# class Type:
#     MESSAGE = 0
#     USER = 1
#     CHANNEL = 2
#     SERVER = 3


# class Snowflake(BaseModel):
#     snowflake: str
#     resourcetype: int

#     def __str__(self):
#         return str(self.snowflake)

#     def __int__(self):
#         return int(str(self.snowflake))


def raise_inline(message: str) -> Exception:
    raise Exception(message)


def b64tostr(b64: Base64) -> str:
    return base64.b64encode(b64.decode()).decode("utf-8")


class Channel(BaseModel):
    name: str
    picture: Optional[str]
    snowflake: str
    message_count: int

    # @classmethod
    # def __str__(self) -> str:
    #     return str(self.snowflake)

    @staticmethod
    @sync_cache()
    def from_prisma(channel: models.Channel, level: int = 0):
        message_count = 0
        if channel.messages is not None:
            message_count = len(channel.messages)
        else:
            if level == 0:
                raise_inline("NO MESSAGES IN CHANNEL SET")
        channel = Channel(
            name=channel.name,
            picture=b64tostr(channel.picture),
            snowflake=str(channel.snowflake),
            message_count=message_count,
        )
        return channel


class _EMPTY:
    @staticmethod
    def count():
        print("empty")
        return 0


class User(BaseModel):
    snowflake: str
    name: str
    email: Optional[str]
    picture: Optional[str]
    friends: Optional[list]
    servers: Optional[list]

    # @classmethod
    # def __str__(self) -> str:
    #     return str(self.snowflake)

    @staticmethod
    @sync_cache()
    def from_prisma(user: models.User, level: int = 0):
        # print(level)
        # print(user)
        # print(user.name)
        return User(
            snowflake=str(user.snowflake),
            name=user.name,
            email=user.email if level == 0 else None,
            picture=b64tostr(user.picture),
            friends=[
                User.from_prisma(x or raise_inline("NO FRIEND IN USER SET"), 1)
                for x in user.friends or []
            ]
            if level == 0
            else None,
            servers=[
                Server.from_prisma(x.server or raise_inline("NO SERVER IN USER SET"), 1)
                for x in user.inServers or []
            ]
            if level == 0
            else None,
        )


class Message(BaseModel):
    content: str
    snowflake: str
    channel: Channel
    author: User

    # @classmethod
    # def __str__(self) -> str:
    #     print("message")
    #     return str(self.snowflake)

    @staticmethod
    @sync_cache()
    def from_prisma(message: models.Message):
        return Message(
            content=message.content,
            snowflake=str(message.snowflake),
            channel=Channel.from_prisma(
                message.channel or raise_inline("NO CHANNEL IN MESAGE SET"), 1
            ),
            author=User.from_prisma(
                message.author or raise_inline("NO AUTHOR IN MESSAGE SET"), 1
            ),
        )


class Server(BaseModel):
    name: str
    picture: Optional[str]
    owner: User
    snowflake: str
    channels: list[Channel]
    members: list[User]
    invites: list[str]

    # @classmethod
    # def __str__(self) -> str:
    #     return str(self.snowflake)

    @staticmethod
    @sync_cache()
    def from_prisma(server: models.Server, level: int = 0):
        return Server(
            name=server.name,
            picture=b64tostr(server.picture),
            owner=User.from_prisma(
                server.owner or raise_inline("NO OWNER IN SERVER SET"), 1
            ),
            snowflake=str(server.snowflake),
            channels=[
                Channel.from_prisma(x or raise_inline("NO CHANNEL IN SERVER SET"), 1)
                for x in server.channels or []
            ],
            members=[
                User.from_prisma(x.user or raise_inline("NO MEMBERS IN SERVER SET"), 1)
                for x in server.members or []
            ],
            invites=[x.invite for x in server.invites or []] if level == 0 else [],
        )


class Session(BaseModel):
    token: str
    session_name: str
    user: User

    # @classmethod
    # def __str__(self) -> str:
    #     return self.user.snowflake

    @staticmethod
    @sync_cache()
    def from_prisma(session: models.Session):
        return Session(
            token=session.token,
            session_name=session.session_name,
            user=User.from_prisma(
                session.user or raise_inline("NO USER IN SESSION SET")
            ),
        )


# class Error:
#     class Invalid:
#         class Type(Exception):
#             error: str = "Invalid snowflake type"

#         class Password(Exception):
#             error: str = "Password is invalid"

#         class Input(Exception):
#             error: str = "Input is invalid"

#     class IncorrectPassword(Exception):
#         error: str = "Password is incorrect"

#     class Unauthorized(Exception):
#         error: str = "You are not authorized"

#     class NotExist:
#         class User(Exception):
#             error: str = "User does not exist"
#             code: int = 404

#         class Snowflake(Exception):
#             error: str = "Snowflake does not exist"
#             code: int = 404

#         class Session(Exception):
#             error: str = "Session does not exist"
#             code: int = 404


class Error(Exception):
    pass


class Header:
    class Token(BaseModel):
        x_token: str


class Response:
    class Success(BaseModel):
        response: str

    class InputError(BaseModel):
        response: str


class Option:
    class MessagesQuery(BaseModel):
        limit: Optional[int] = None
        before: Optional[str] = None

    class Password(BaseModel):
        password: str

    class Username(BaseModel):
        username: str


class Create:
    class Channel(BaseModel):
        name: str
        picture: Optional[bytes]

    class Message(BaseModel):
        content: str

    class Server(BaseModel):
        name: str
        # picture_url: Optional[str]

    class User(BaseModel):
        username: str
        password: str
        email: str

    class Session(BaseModel):
        session_name: str
        email: str
        password: str


class List:
    class Messages(BaseModel):
        messages: list[Optional[Message]]

    class Servers(BaseModel):
        servers: list[Server]

    class Sessions(BaseModel):
        sessions: list[Session]

    class Users(BaseModel):
        users: list[User]

    class Channels(BaseModel):
        channels: list[Channel]


class Update:
    class User(BaseModel):
        name: Optional[str]
        picture: Optional[str]
        password: Optional[str]
        email: Optional[str]

    class Password(BaseModel):
        password: str
        new_password: str

    class Channel(BaseModel):
        name: Optional[str]
        picture: Optional[str]
