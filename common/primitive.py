from pydantic import BaseModel
from typing import Optional


class Channel(BaseModel):
    name: str
    picture: Optional[str]
    snowflake: str
    message_count: int


class User(BaseModel):
    snowflake: str
    username: str
    nickname: Optional[str]
    picture: Optional[str]


class Message(BaseModel):
    content: str
    snowflake: str
    channel_snowflake: str
    author: User


class Server(BaseModel):
    name: str
    picture: Optional[str]
    owner: User
    snowflake: str
    channels: list[Channel]


class Session(BaseModel):
    token: str
    session_name: str


class Error:
    class Unauthorized(BaseModel):
        error: str

    class InvalidInput(BaseModel):
        error: str

    class InvalidSnowflake(BaseModel):
        error: str

    class AlreadyExists(BaseModel):
        error: str

    class DoesNotExist(BaseModel):
        error: str

    class Ratelimited(BaseModel):
        error: str


class Header:
    class Token(BaseModel):
        x_token: str


class Response:
    class Success(BaseModel):
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

    class Token(BaseModel):
        session_name: str
        username: str
        password: str


class List:
    class Messages(BaseModel):
        messages: list[Message]

    class Servers(BaseModel):
        servers: list[Server]

    class Sessions(BaseModel):
        sessions: list[Session]


class Update:
    class User(BaseModel):
        nickname: Optional[str]
        picture: Optional[str]

    class Password(BaseModel):
        password: str
        new_password: str
