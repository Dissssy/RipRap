from curses.ascii import isdigit
from dataclasses import dataclass
from typing import Optional, TypedDict
from quart import Blueprint
from quart import current_app as app
from quart_schema import (
    tag,
    validate_headers,
    validate_querystring,
    validate_request,
    validate_response,
)
from common.db import _get_snowflake_from_token, _get_user_info, _is_user

from common.primitive import Primitive
from common.utils import validate_snowflake

bp = Blueprint("user", __name__)


class User:
    Headers = Primitive.TokenHeader

    @dataclass
    class Info:
        info: TypedDict(
            "User",
            {
                "snowflake": str,
                "username": str,
                "nickname": Optional[str],
                "picture": Optional[str],
            },
        )

    Unauthorized = Primitive.Error
    Error = Primitive.Error
    Added = Primitive.GenericStr
    Requested = Primitive.GenericStr


@bp.get("/")
@tag(["User", "Info"])
@validate_headers(User.Headers)
@validate_response(User.Info, 200)
@validate_response(User.Unauthorized, 401)
async def get_self(headers: User.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        return User.Info(await _get_user_info(app.db, snowflake))
    else:
        return User.Unauthorized("Token is invalid"), 401


@bp.get("/<user_snowflake>")
@tag(["User", "Info"])
@validate_headers(User.Headers)
@validate_response(User.Info, 200)
@validate_response(User.Unauthorized, 401)
@validate_response(User.Error, 400)
async def get_other(user_snowflake: str, headers: User.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if validate_snowflake(user_snowflake):
            user = await _get_user_info(app.db, user_snowflake)
            if user is not None:
                return User.Info(user)
            else:
                return User.Error("User does not exist"), 400
        else:
            return User.Error("Invalid snowflake"), 400
    else:
        return User.Unauthorized("Token is invalid"), 401


@bp.put("/<user_snowflake>/add")
@tag(["User"])
@validate_headers(User.Headers)
@validate_response(User.Added, 200)
@validate_response(User.Requested, 200)
@validate_response(User.Unauthorized, 401)
@validate_response(User.Error, 400)
async def put_friend(user_snowflake: str, headers: User.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if validate_snowflake(user_snowflake):
            if _is_user(user_snowflake):
                user = await _add_friend(app.db, snowflake, user_snowflake)
                if user:
                    return User.Added(f"Successfully added {user_snowflake}")
                else:
                    return User.Requested(f"Successfully requested {user_snowflake}")
            else:
                return User.Error("User does not exist"), 400
        else:
            return User.Error("Invalid snowflake"), 400
    else:
        return User.Unauthorized("Token is invalid"), 401
