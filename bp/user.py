from typing import cast
from quart import Blueprint, render_template
from quart import current_app as app
from quart_schema import (
    tag,
    validate_headers,
    validate_querystring,
    validate_request,
    validate_response,
)


from common.primitive import User, Session, Response
from common.utils import auth, benchmark, validate_snowflake

bp = Blueprint("user", __name__)

# GET / (user info)
#     200 OK - Returns user object
#     401 Unauthorized - Token invalid
#     500 Internal Server Error


@bp.get("/")
@tag(["User", "Info", "Authed", "Self"])
@benchmark()
@auth()
@validate_response(User, 200)
async def user_info_self(session: Session) -> User:
    """Get user info."""
    return await app.db.user_get(snowflake=session.user.snowflake, level=0)


# GET /<user_snowflake>/ (another users info, only if friends or in mutual server)
#     200 OK - Returns user object
#     401 Unauthorized - Token invalid
#     404 Not Found - User not found
#     500 Internal Server Error


@bp.get("/<user_snowflake>/")
@tag(["User", "Info", "Authed"])
@benchmark()
@auth()
@validate_response(User, 200)
async def user_info_other(session: Session, user_snowflake: str) -> User:
    """Get user info."""
    user = await app.db.user_get(snowflake=user_snowflake)
    return user


# PUT /<user_snowflake>/friends (send request or confirm request
#     200 OK - Returns nothing
#     401 Unauthorized - Token invalid
#     404 Not Found - User not found
#     500 Internal Server Error


# @bp.put("/<user_snowflake>/friends")
# @tag(["User", "Creation", "Friends", "Authed"])
# @benchmark()
# @auth()
# @validate_response(Response.Success, 200)
# async def user_friends_add(session: Session, user_snowflake: str) -> Response.Success:
#     """Add a friend."""
#     await app.db.friend_set(
#         user_snowflake=session.user.snowflake, friend_snowflake=user_snowflake, status="pending"
#     )
#     return Response.Success(response="Successfully sent friend request.")


# DELETE /<user_snowflake>/friends (delete request or remove friend)
#     200 OK - Returns nothing
#     401 Unauthorized - Token invalid
#     404 Not Found - User not found
#     500 Internal Server Error


# GET /requests
#     200 OK - Returns list of all requests
#     401 Unauthorized - Token invalid
#     500 Internal Server Error


@bp.get("/usercard")
@tag(["Auth", "Helper"])
@benchmark()
@auth()
async def auth_image(session: Session):
    user = await app.db.user_get(snowflake=session.user.snowflake, level=0)
    return await render_template(
        "/usercard.html",
        image=user.picture,
        snowflake=user.snowflake,
        name=user.name,
        email=user.email,
        friends=len(user.friends),
        servers=len(user.servers),
    )


# @bp.get("/")
# @tag(["User", "Info"])
# @validate_response(Primitive.User, 200)
# @auth()
# async def get_self(session: Primitive.Session) -> Primitive.User:
#     """Get information about the current user."""
#     return session.user


# @bp.patch("/")
# @tag(["User", "Update"])
# @auth()
# @validate_request(Primitive.Update.User)
# @validate_response(Primitive.User, 200)
# async def update_self(session: Primitive.Session, update: Primitive.Update.User) -> Primitive.User:
#     """Update the current user."""
#     return await app.db.user_set(session.snowflake, nickname=update.nickname, picture=update.picture)

# @bp.get("/<user_snowflake>")
# @tag(["User", "Info"])
# @auth()
# @validate_response(Primitive.User, 200)
# async def get_user(session: Primitive.Session, user_snowflake: str) -> Primitive.User:
#     """Get information about a user."""
#     return await app.db.user_get(await app.db.snowflake_get(user_snowflake))

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
