import codecs
from typing import cast
import zlib
import bcrypt
from quart import Blueprint
from quart import current_app as app
from quart_schema import tag, validate_request, validate_response
from common.primitive import Create, List, Response, Server, Session
from common.utils import auth, benchmark, validate_string, websocket

bp = Blueprint("server", __name__)

# GET / (list all servers)
#     200 OK - Returns list of all servers
#     401 Unauthorized - Token invalid
#     500 Internal Server Error


@bp.get("/")
@tag(["Server", "Info", "Authed"])
@benchmark()
@auth()
@validate_response(List.Servers, 200)
async def server_list(session: Session) -> List.Servers:
    """Get list of all servers."""
    return List.Servers(
        servers=(
            await app.db.user_get(snowflake=session.user.snowflake, level=0)
        ).servers
    )


# GET /<server_snowflake>/ (server info if server exists)
#     200 OK - Returns server object
#     401 Unauthorized - Token invalid
#     404 Not Found - Server not found
#     500 Internal Server Error


@bp.get("/<server_snowflake>/")
@tag(["Server", "Info", "Authed"])
@benchmark()
@auth()
@validate_response(Server, 200)
async def server_info(session: Session, server_snowflake: str) -> Server:
    """Get server info."""
    return await app.db.server_get(snowflake=server_snowflake, user=session.user)


# PUT / (create server)
#     201 Created - Server created - returns server object
#     401 Unauthorized - Token invalid
#     400 Bad Request - Input error
#     500 Internal Server Error


@bp.put("/")
@tag(["Server", "Creation", "Authed"])
@benchmark()
@auth()
@validate_request(Create.Server)
@validate_response(Server, 201)
async def server_create(session: Session, data: Create.Server) -> Server:
    """Create server."""
    return await app.db.server_set(
        name=data.name,
        user=session.user,
    )


# DELETE /<server_snowflake>/ (delete server if owner)
#     200 OK - Server deleted - returns nothing
#     401 Unauthorized - Token invalid
#     404 Not Found - Server not found
#     500 Internal Server Error


@bp.delete("/<server_snowflake>/")
@tag(["Server", "Deletion", "Authed"])
@benchmark()
@auth()
# @websocket(303, {"server_snowflake": str})
@validate_response(Response.Success, 204)
async def server_delete(session: Session, server_snowflake: str) -> Response.Success:
    """Delete server."""
    await app.db.server_set(snowflake=server_snowflake, user=session.user, delete=True)
    return Response.Success(response="Server deleted")


# DELETE /<server_snowflake>/members/<user_snowflake> (remove user from server if owner or leave server if user)
#     200 OK - User removed - returns nothing
#     401 Unauthorized - Token invalid
#     404 Not Found - Server or user not found
#     500 Internal Server Error


@bp.delete("/<server_snowflake>/members/<user_snowflake>")
@tag(["Server", "User", "Deletion", "Authed"])
@benchmark()
@auth()
@validate_response(Response.Success, 204)
async def server_user_delete(
    session: Session, server_snowflake: str, user_snowflake: str
) -> Response.Success:
    """Remove user from server."""
    await app.db.member_set(
        user=session.user,
        server=await app.db.server_get(snowflake=server_snowflake, user=session.user),
        member=user_snowflake,
    )
    return Response.Success(response="User removed")


# @bp.get("/list")
# @tag(["Servers", "Info", "Listing"])
# @validate_response(Primitive.List.Servers, 200)
# @auth()
# async def server_userlist(session: Primitive.Session):
#     return await app.db.user_list_servers(user=session.snowflake), 200


# @bp.put("/create")
# @tag(["Servers", "Creation"])
# @auth()
# @validate_request(Primitive.Create.Server)
# @validate_response(Primitive.Server, 200)
# async def server_make(data: Primitive.Create.Server, session: Primitive.Session):
#     validate_string(data.name, minlength=1, maxlength=100)
#     if data.picture_url is not None:
#         validate_string(data.picture_url, minlength=1, maxlength=100)
#     return await app.db.server_create(
#         await app.db.user_get(session.snowflake), data.name, data.picture_url
#     )


# @bp.get("/<server_snowflake>")
# @tag(["Servers", "Info"])
# @auth()
# @validate_response(Primitive.Server, 200)
# async def server_info(server_snowflake: str, session: Primitive.Session):
#     user_servers = [
#         str(x.snowflake)
#         for x in (
#             await app.db.user_list_servers(await app.db.user_get(session.snowflake))
#         ).servers
#     ]
#     if server_snowflake not in user_servers:
#         raise Primitive.Error("Server not found", 404)
#     return await app.db.server_get(await app.db.snowflake_get(server_snowflake)), 200


# @bp.delete("/<server_snowflake>")
# @tag(["Servers", "Deletion"])
# @auth()
# @validate_request(Primitive.Option.Password)
# @validate_response(Primitive.Response.Success, 200)
# async def server_delete(
#     server_snowflake: str,
#     data: Primitive.Option.Password,
#     session: Primitive.Session,
# ):
#     await app.db.validate_password(
#         await app.db.user_get(session.snowflake, nocache=True), data.password
#     )
#     user_servers = {}
#     for x in (
#         await app.db.user_list_servers(await app.db.user_get(session.snowflake))
#     ).servers:
#         user_servers[str(x.snowflake)] = str(x.owner.snowflake)
#     if server_snowflake not in user_servers.keys():
#         raise Primitive.Error("Server not found", 404)
#     if user_servers[str(x.snowflake)] != str(session.snowflake):
#         raise Primitive.Error("You are not the owner of this server", 403)
#     await app.db.server_remove(await app.db.snowflake_get(server_snowflake))
#     return Primitive.Response.Success(response="Server deleted"), 200
