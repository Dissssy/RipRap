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


import common.primitive as Primitive
from common.utils import auth, validate_snowflake

bp = Blueprint("user", __name__)


@bp.get("/")
@tag(["User", "Info"])
@validate_response(Primitive.User, 200)
@auth()
async def get_self(session: Primitive.Session) -> Primitive.User:
    """Get information about the current user."""
    return await app.db.user_get(session.snowflake)

@bp.patch("/")
@tag(["User", "Update"])
@auth()
@validate_request(Primitive.Update.User)
@validate_response(Primitive.User, 200)
async def update_self(session: Primitive.Session, update: Primitive.Update.User) -> Primitive.User:
    """Update the current user."""
    return await app.db.user_set(session.snowflake, nickname=update.nickname, picture=update.picture)

@bp.get("/<user_snowflake>")
@tag(["User", "Info"])
@auth()
@validate_response(Primitive.User, 200)
async def get_user(session: Primitive.Session, user_snowflake: str) -> Primitive.User:
    """Get information about a user."""
    return await app.db.user_get(await app.db.snowflake_get(user_snowflake))

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
