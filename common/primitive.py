from dataclasses import dataclass
from typing import TypedDict


class Primitive:
    @dataclass
    class Error:
        error: str

    @dataclass
    class TokenHeader:
        x_token: str

    @dataclass
    class Snowflake:
        snowflake: str

    @dataclass
    class Token:
        token: str

    @dataclass
    class GenericStr:
        response: str

    @dataclass
    class GenericList:
        response: list
