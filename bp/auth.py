import base64
import codecs
import zlib
import bcrypt
from quart import Blueprint, render_template
from quart import current_app as app


from quart_schema import tag, validate_headers, validate_request, validate_response
from common.db import RIPRAPDatabase

from common.primitive import (
    User,
    Create,
    Response,
    Session,
    Error,
    Header,
    Option,
    List,
)
from common.utils import auth, benchmark, ratelimit, validate_string

bp = Blueprint("auth", __name__)

# PUT /register
#     201 Created - User created - returns user object
#     400 Bad Request - User already exists
#     400 Bad Request - Input error
#     500 Internal Server Error


@bp.put("/register")
@tag(["Auth", "Creation", "User"])
@benchmark()
@validate_request(Create.User)
@validate_response(User, 201)
async def auth_register(data: Create.User) -> User:
    """Register a new user."""
    validate_string(data.username, minlength=1, maxlength=32)
    validate_string(data.password, minlength=8, maxlength=64)

    user = await app.db.user_set(
        name=data.username, password=data.password, email=data.email
    )
    return user


# PUT /session (LOGIN)
#     201 Created - User logged in - returns session object
#     404 Not Found - User not found
#     401 Unauthorized - Wrong input
#     500 Internal Server Error


@bp.put("/session")
@tag(["Auth", "Creation", "Session"])
@benchmark()
@validate_request(Create.Session)
@validate_response(Session, 201)
async def auth_session(data: Create.Session) -> Session:
    """Create a new session for a user."""
    validate_string(data.session_name, minlength=1, maxlength=128)
    validate_string(data.password, minlength=8, maxlength=64)
    app.db._verify_email(data.email)

    session = await app.db.session_set(
        session_name=data.session_name,
        password=data.password,
        email=data.email,
    )
    return session


# DELETE /session (LOGOUT)
#     200 OK - User logged out - returns nothing
#     401 Unauthorized - Token invalid
#     500 Internal Server Error


@bp.delete("/session")
@tag(["Auth", "Deletion", "Session", "Authed"])
@benchmark()
@auth()
@validate_response(Response.Success, 200)
async def auth_session_delete(session: Session) -> Response.Success:
    """Delete a session."""
    await app.db.session_set(token=session.token)
    return Response.Success(response="Successfully invalidated session.")


# GET /session (list all)
#     200 OK - Returns list of all sessions
#     401 Unauthorized - Token invalid
#     500 Internal Server Error


@bp.get("/session")
@tag(["Auth", "Info", "Session", "Authed"])
@benchmark()
@auth()
@validate_response(List.Sessions, 200)
async def auth_session_list(session: Session) -> List.Sessions:
    """List all sessions."""
    return List.Sessions(
        sessions=await app.db.session_get(token=session.token, listall=True)
    )


# @bp.put("/register")
# @tag(["Auth", "Creation"])
# @validate_request(Create.User)
# @validate_response(User, 201)
# @validate_response(Response.InputError, 400)
# async def auth_register(data: Create.User):
#     r = validate_string(data.username, minlength=3, maxlength=32)
#     if r is not None:
#         return Response.InputError(response=r), 400
#     r = validate_string(data.password, minlength=8, maxlength=128)
#     if r is not None:
#         return Response.InputError(response=r), 400
#     return await app.db.user_set(
#         name=data.username, password=data.password, email=data.email
#     )


# # @bp.get("/usercard")
# # @tag(["Auth", "Helper"])
# # @auth()
# # async def auth_image(session: Session):
# #     return await render_template(
# #         "/usercard.html",
# #         image=session.user.picture,
# #         snowflake=session.user.snowflake,
# #         name=session.user.name,
# #         email=session.user.email,
# #         friends=len(session.user.friends),
# #         servers=len(session.user.servers),
# #     )


# @bp.post("/login")
# @tag(["Auth", "Creation"])
# @validate_request(Create.Session)
# @validate_response(Session, 201)
# async def auth_login(data: Create.Session):
#     r = validate_string(data.session_name, minlength=1, maxlength=100)
#     if r is not None:
#         raise Error(r, 400)
#     return await app.db.session_set(
#         email=data.email, password=data.password, session_name=data.session_name
#     )


# @bp.delete("/logout")
# @tag(["Auth", "Deletion"])
# @validate_response(Response.Success, 201)
# @validate_headers(Header.Token)
# async def auth_logout(headers: Header.Token):
#     response: Session = await app.db.session_set(token=headers.x_token)
#     return (
#         Response.Success(
#             response=f"Successfully invalidated token for session {response.session_name}"
#         ),
#         201,
#     )


# @bp.get("/sessions")
# @tag(["Auth", "Info"])
# @auth()
# @validate_response(List.Sessions, 200)
# async def auth_sessions(session: Session):
#     return (
#         await app.db.session_get(session.token, listall=True),
#         200,
#     )


# @bp.delete("/account")
# @tag(["Auth", "Deletion"])
# @validate_request(Option.Password)
# @validate_response(Response.Success, 204)
# @auth()
# async def auth_remove(data: Option.Password, session: Session):
#     d = await app.db.user_set(
#         snowflake=session.user.snowflake, password=data.password, delete=True
#     )
#     for wssnowflake in app.ws:
#         app.ws[wssnowflake].append({"code": "201", "data": d})
#     return (
#         Response.Success(response="Dont let the door hit you on the way out"),
#         201,
#     )
