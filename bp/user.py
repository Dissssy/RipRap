from typing import cast
from quart import Blueprint
from quart import current_app as app
from quart_schema import (
    tag,
    validate_headers,
    validate_querystring,
    validate_request,
    validate_response,
)
from common.db import (
    _get_snowflake_from_token,
    _get_user_info,
    _is_user,
    _update_user_info,
)

import common.primitive as Primitive
from common.utils import validate_snowflake

bp = Blueprint("user", __name__)


@bp.get("/")
@tag(["User", "Info"])
@validate_headers(Primitive.Header.Token)
@validate_response(Primitive.User, 200)
@validate_response(Primitive.Error.Unauthorized, 401)
async def get_self(headers: Primitive.Header.Token):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        return cast(Primitive.User, await _get_user_info(app.db, snowflake))
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


@bp.patch("/")
@tag(["User", "Update"])
@validate_headers(Primitive.Header.Token)
@validate_request(Primitive.Update.User)
@validate_response(Primitive.User, 200)
@validate_response(Primitive.Error.Unauthorized, 401)
async def patch_self(data: Primitive.Update.User, headers: Primitive.Header.Token):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        return cast(
            Primitive.User,
            await _update_user_info(app.db, snowflake, data.nickname, data.picture),
        )
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


@bp.get("/<user_snowflake>")
@tag(["User", "Info"])
@validate_headers(Primitive.Header.Token)
@validate_response(Primitive.User, 200)
@validate_response(Primitive.Error.Unauthorized, 401)
@validate_response(Primitive.Error.InvalidInput, 400)
@validate_response(Primitive.Error.DoesNotExist, 404)
async def get_other(user_snowflake: str, headers: Primitive.Header.Token):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if validate_snowflake(user_snowflake):
            user = await _get_user_info(app.db, user_snowflake)
            if user is not None:
                return cast(Primitive.User, user)
            else:
                return Primitive.Error.DoesNotExist("User does not exist"), 404
        else:
            return Primitive.Error.InvalidInput("Invalid snowflake"), 400
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


# @bp.put("/<user_snowflake>/add")
# @tag(["User"])
# @validate_headers(User.Headers)
# @validate_response(User.Added, 200)
# @validate_response(User.Requested, 200)
# @validate_response(User.Unauthorized, 401)
# @validate_response(User.Error, 400)
# async def put_friend(user_snowflake: str, headers: User.Headers):
#     snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
#     if snowflake is not None:
#         if validate_snowflake(user_snowflake):
#             if _is_user(user_snowflake):
#                 user = await _add_friend(app.db, snowflake, user_snowflake)
#                 if user:
#                     return User.Added(f"Successfully added {user_snowflake}")
#                 else:
#                     return User.Requested(f"Successfully requested {user_snowflake}")
#             else:
#                 return User.Error("User does not exist"), 400
#         else:
#             return User.Error("Invalid snowflake"), 400
#     else:
#         return User.Unauthorized("Token is invalid"), 401
