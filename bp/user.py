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


from common.primitive import Update, User, Session, Response
from common.utils import auth, benchmark, validate_snowflake

bp = Blueprint("user", __name__)

# GET / (user info)
#     200 OK - Returns user object
#     401 Unauthorized - Token invalid
#     500 Internal Server Error


@bp.get("/")
@tag(["User", "Info", "Self"])
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
@tag(["User", "Info"])
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


@bp.get("/card/")
@tag(["Card"])
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


# PATCH / (update user info)
#     200 OK - Returns nothing
#     401 Unauthorized - Token invalid
#     500 Internal Server Error


@bp.patch("/")
@tag(["User", "Update", "Self"])
@benchmark()
@auth()
@validate_request(Update.User)
@validate_response(Response.Success, 200)
async def user_update_self(session: Session, data: Update.User) -> Response.Success:
    """Update user info."""
    await app.db.user_set(
        snowflake=session.user.snowflake,
        password=data.oldpassword,
        name=data.name,
        picture=data.picture,
    )
    # get all members of all servers user is in, get all of their tokens, and post a websocket event to all tokens

    return Response.Success(response="Successfully updated user.")
