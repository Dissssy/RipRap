from pydantic import BaseModel
from typing import Optional


class Type:
    MESSAGE = 0
    USER = 1
    CHANNEL = 2
    SERVER = 3


class Snowflake(BaseModel):
    snowflake: str
    resourcetype: int

    def __str__(self):
        return self.snowflake

    def __int__(self):
        return int(self.snowflake)


class Channel(BaseModel):
    name: str
    picture: Optional[str]
    snowflake: Snowflake
    message_count: int


class User(BaseModel):
    snowflake: Snowflake
    username: str
    nickname: Optional[str]
    picture: Optional[str]
    passwordhash: Optional[bytes]


class Message(BaseModel):
    content: str
    snowflake: Snowflake
    channel: Channel
    author: User


class Server(BaseModel):
    name: str
    picture: Optional[str]
    owner: User
    snowflake: Snowflake
    channels: list[Channel]
    users: list[User]


class Session(BaseModel):
    token: str
    session_name: str
    snowflake: Snowflake


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
        picture_url: Optional[str]

    class Message(BaseModel):
        content: str

    class Server(BaseModel):
        name: str
        picture_url: Optional[str]

    class User(BaseModel):
        nickname: Optional[str]
        picture: Optional[str]
        username: str
        password: str

    class Session(BaseModel):
        session_name: str
        username: str
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
        nickname: Optional[str]
        picture: Optional[str]

    class Password(BaseModel):
        password: str
        new_password: str

    class Channel(BaseModel):
        name: Optional[str]
        picture: Optional[str]
