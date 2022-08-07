from dataclasses import dataclass
from typing import Optional


@dataclass
class Channel:
    name: str
    picture: Optional[str]
    snowflake: str
    message_count: int


@dataclass
class User:
    snowflake: str
    username: str
    nickname: Optional[str]
    picture: Optional[str]


@dataclass
class Message:
    content: str
    snowflake: str
    author: User


@dataclass
class Server:
    name: str
    picture: Optional[str]
    owner: User
    snowflake: str
    channels: list[Channel]


@dataclass
class Session:
    token: str
    session_name: str


class Error:
    @dataclass
    class Unauthorized:
        error: str

    @dataclass
    class InvalidInput:
        error: str

    @dataclass
    class InvalidSnowflake:
        error: str

    @dataclass
    class AlreadyExists:
        error: str

    @dataclass
    class DoesNotExist:
        error: str

    @dataclass
    class Ratelimited:
        error: str


class Header:
    @dataclass
    class Token:
        x_token: str


class Response:
    @dataclass
    class Success:
        response: str


class Option:
    @dataclass
    class MessagesQuery:
        limit: Optional[int] = None
        before: Optional[str] = None

    @dataclass
    class Password:
        password: str

    @dataclass
    class Username:
        username: str


class Create:
    @dataclass
    class Channel:
        name: str
        picture_url: Optional[str]

    @dataclass
    class Message:
        content: str

    @dataclass
    class Server:
        name: str
        picture_url: Optional[str]

    @dataclass
    class User(Option.Username, Option.Password):
        nickname: Optional[str]
        picture: Optional[str]

    @dataclass
    class Token(Option.Username, Option.Password):
        session_name: str


class List:
    @dataclass
    class Messages:
        messages: list[Message]

    @dataclass
    class Servers:
        servers: list[Server]

    @dataclass
    class Sessions:
        sessions: list[Session]


class Update:
    @dataclass
    class User:
        nickname: Optional[str]
        picture: Optional[str]

    @dataclass
    class Password:
        password: str
        new_password: str
