import codecs
from time import time
from typing import cast
import zlib
import bcrypt
from quart import Blueprint
from quart import current_app as app
from quart_schema import (
    tag,
    validate_headers,
    validate_querystring,
    validate_request,
    validate_response,
)

from common.primitive import Create, List, Response, Server, Session, Channel
from common.utils import auth, benchmark, ratelimit, validate_snowflake, validate_string

bp = Blueprint("channel", __name__)

# GET /<server_snowflake>/ (list all channels in server if user is in server)
#     200 OK - Returns list of all channels
#     401 Unauthorized - Token invalid
#     404 Not Found - Server not found
#     500 Internal Server Error


# @bp.get("/<server_snowflake>")
# @tag(["Channel", "Info"])
# @benchmark()
# @auth()
# @validate_response(List.Channels, 200)
# async def channel_list(session: Session, server_snowflake: str) -> List.Channels:
#     """Get list of all channels in a server."""
#     return List.Channels(
#         channels=(
#             await app.db.server_get(snowflake=server_snowflake, user=session.user)
#         ).channels
#     )


# GET /<server_snowflake>/<channel_snowflake>/ (channel info if channel exists and user is in server)
#     200 OK - Returns channel object
#     401 Unauthorized - Token invalid
#     404 Not Found - Server or channel not found
#     500 Internal Server Error


@bp.get("/<channel_snowflake>/")
@tag(["Channel", "Info"])
@benchmark()
@auth()
@validate_response(Channel, 200)
async def channel_info(session: Session, channel_snowflake: str) -> Channel:
    """Get channel info."""
    return await app.db.channel_get(
        channel_snowflake=channel_snowflake, user=session.user
    )


# PUT /<server_snowflake>/ (create channel if user is owner)
#     201 Created - Channel created - returns channel object
#     401 Unauthorized - Token invalid
#     401 Unauthorized - User is not owner
#     404 Not Found - Server not found
#     400 Bad Request - Input error
#     500 Internal Server Error


@bp.put("/<server_snowflake>/")
@tag(["Channel", "Create"])
@benchmark()
@auth()
@validate_request(Create.Channel)
@validate_response(Channel, 201)
async def channel_create(
    session: Session, server_snowflake: str, data: Create.Channel
) -> Channel:
    """Create a channel."""
    return await app.db.channel_set(
        user=session.user,
        server=await app.db.server_get(snowflake=server_snowflake, user=session.user),
        name=data.name,
    )


# DELETE /<server_snowflake>/<channel_snowflake>/ (delete channel if user is owner)
#     200 OK - Channel deleted - returns nothing
#     401 Unauthorized - Token invalid
#     401 Unauthorized - User is not owner
#     404 Not Found - Server or channel not found
#     500 Internal Server Error


@bp.delete("/<server_snowflake>/<channel_snowflake>/")
@tag(["Channel", "Delete"])
@benchmark()
@auth()
@validate_response(Response.Success, 200)
async def channel_delete(
    session: Session, server_snowflake: str, channel_snowflake: str
) -> Response:
    """Delete a channel."""
    await app.db.channel_set(
        user=session.user,
        server=await app.db.server_get(snowflake=server_snowflake, user=session.user),
        snowflake=channel_snowflake,
        delete=True,
    )
    return Response.Success(response="Channel deleted")


# @bp.put("/<server_snowflake>/create")
# @tag(["Channels", "Servers", "Creation"])
# @validate_request(Primitive.Create.Channel)
# @validate_response(Primitive.Channel, 200)
# # @ratelimit(time=3000, quantity=3)
# @auth()
# async def channel_make(
#     server_snowflake: str, data: Primitive.Create.Channel, session: Primitive.Session
# ):
#     server = await app.db.server_get(await app.db.snowflake_get(server_snowflake))
#     if str(server.owner.snowflake) != str(session.snowflake):
#         raise Primitive.Error("You are not the owner of this server!", 403)
#     return await app.db.channel_create(
#         server=server,
#         name=data.name,
#         picture_url=data.picture_url,
#     )


# @bp.get("/<channel_snowflake>")
# @tag(["Channels", "Info"])
# @validate_response(Primitive.Channel, 200)
# @auth()
# async def channel_get(channel_snowflake: str, session: Primitive.Session):
#     user_channels = [
#         str(x.snowflake)
#         for x in (
#             await app.db.user_list_channels(await app.db.user_get(session.snowflake))
#         ).channels
#     ]
#     if channel_snowflake not in user_channels:
#         raise Primitive.Error("Channel not found", 404)
#     return await app.db.channel_get(await app.db.snowflake_get(channel_snowflake)), 200


# @bp.delete("/<server_snowflake>/<channel_snowflake>")
# @tag(["Channels", "Deletion"])
# @auth()
# @validate_request(Primitive.Option.Password)
# @validate_response(Primitive.Response.Success, 200)
# async def channel_delete(
#     server_snowflake: str,
#     channel_snowflake: str,
#     data: Primitive.Option.Password,
#     session: Primitive.Session,
# ):
#     await app.db.validate_password(
#         await app.db.user_get(session.snowflake), data.password
#     )
#     server = await app.db.server_get(await app.db.snowflake_get(server_snowflake))
#     if str(server.owner.snowflake) != str(session.snowflake):
#         raise Primitive.Error("You are not the owner of this server!", 403)
#     return (
#         await app.db.channel_remove(
#             await app.db.channel_get(await app.db.snowflake_get(channel_snowflake))
#         ),
#         200,
#     )


# @bp.put("/<server_snowflake>/<channel_snowflake>/edit")
# @tag(["Channels", "Editing"])
# @auth()
# @validate_request(Primitive.Update.Channel)
# @validate_response(Primitive.Channel, 200)
# async def channel_edit(
#     server_snowflake: str,
#     channel_snowflake: str,
#     data: Primitive.Update.Channel,
#     session: Primitive.Session,
# ):
#     server = await app.db.server_get(await app.db.snowflake_get(server_snowflake))
#     if str(server.owner.snowflake) != str(session.snowflake):
#         raise Primitive.Error("You are not the owner of this server!", 403)
#     return await app.db.channel_update(
#         await app.db.channel_get(await app.db.snowflake_get(channel_snowflake)),
#         name=data.name,
#         picture_url=data.picture,
#     )


# @bp.put("/<channel_snowflake>/messages")
# @tag(["Channels", "Messages", "Creation"])
# @auth()
# @validate_request(Primitive.Create.Message)
# @validate_response(Primitive.Message, 200)
# async def channel_message_make(
#     channel_snowflake: str, data: Primitive.Create.Message, session: Primitive.Session
# ):
#     # if channel is in user's channels create message
#     user_channels = [
#         str(x.snowflake)
#         for x in (
#             await app.db.user_list_channels(await app.db.user_get(session.snowflake))
#         ).channels
#     ]
#     if channel_snowflake not in user_channels:
#         raise Primitive.Error("Channel not found", 404)
#     return await app.db.message_create(
#         channel=await app.db.channel_get(await app.db.snowflake_get(channel_snowflake)),
#         content=data.content,
#         author=await app.db.user_get(session.snowflake),
#     )


# @bp.get("/<channel_snowflake>/messages")
# @tag(["Channels", "Messages", "Listing"])
# @auth()
# @validate_response(Primitive.List.Messages, 200)
# @validate_querystring(Primitive.Option.MessagesQuery)
# async def channel_message_list(
#     channel_snowflake: str,
#     session: Primitive.Session,
#     query_args: Primitive.Option.MessagesQuery,
# ):
#     user_channels = [
#         str(x.snowflake)
#         for x in (
#             await app.db.user_list_channels(await app.db.user_get(session.snowflake))
#         ).channels
#     ]
#     if query_args.before is not None:
#         msg = await app.db.message_get(await app.db.snowflake_get(query_args.before))
#         if str(msg.channel.snowflake) != channel_snowflake:
#             raise Primitive.Error("Before message not found", 404)

#     if channel_snowflake not in user_channels:
#         raise Primitive.Error("Channel not found", 404)
#     response = await app.db.channel_list_messages(
#         await app.db.channel_get(await app.db.snowflake_get(channel_snowflake)),
#         limit=query_args.limit,
#         before=int(query_args.before) if query_args.before is not None else None,
#     )
#     return response, 200


# @bp.delete("/<channel_snowflake>/messages/<message_snowflake>")
# @tag(["Channels", "Messages", "Deletion"])
# @auth()
# @validate_response(Primitive.Response.Success, 200)
# async def channel_message_delete(
#     channel_snowflake: str,
#     message_snowflake: str,
#     session: Primitive.Session,
# ):
#     user_channels = [
#         str(x.snowflake)
#         for x in (
#             await app.db.user_list_channels(await app.db.user_get(session.snowflake))
#         ).channels
#     ]
#     if channel_snowflake not in user_channels:
#         raise Primitive.Error("Channel not found", 404)
#     await app.db.message_remove(
#         await app.db.message_get(await app.db.snowflake_get(message_snowflake))
#     )
#     return (Primitive.Response.Success(response="Successfully removed message"), 200)
