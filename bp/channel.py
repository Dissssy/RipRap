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

import common.primitive as Primitive
from common.utils import auth, ratelimit, validate_snowflake, validate_string

bp = Blueprint("channel", __name__)


@bp.put("/<server_snowflake>/create")
@tag(["Channels", "Servers", "Creation"])
@validate_request(Primitive.Create.Channel)
@validate_response(Primitive.Channel, 200)
# @ratelimit(time=3000, quantity=3)
@auth()
async def channel_make(
    server_snowflake: str, data: Primitive.Create.Channel, session: Primitive.Session
):
    server = await app.db.server_get(await app.db.snowflake_get(server_snowflake))
    if str(server.owner.snowflake) != str(session.snowflake):
        raise Primitive.Error("You are not the owner of this server!", 403)
    return await app.db.channel_create(
        server=server,
        name=data.name,
        picture_url=data.picture_url,
    )


@bp.get("/<channel_snowflake>")
@tag(["Channels", "Info"])
@validate_response(Primitive.Channel, 200)
@auth()
async def channel_get(channel_snowflake: str, session: Primitive.Session):
    user_channels = [
        str(x.snowflake)
        for x in (
            await app.db.user_list_channels(await app.db.user_get(session.snowflake))
        ).channels
    ]
    if channel_snowflake not in user_channels:
        raise Primitive.Error("Channel not found", 404)
    return await app.db.channel_get(await app.db.snowflake_get(channel_snowflake)), 200


@bp.delete("/<server_snowflake>/<channel_snowflake>")
@tag(["Channels", "Deletion"])
@auth()
@validate_request(Primitive.Option.Password)
@validate_response(Primitive.Response.Success, 200)
async def channel_delete(
    server_snowflake: str,
    channel_snowflake: str,
    data: Primitive.Option.Password,
    session: Primitive.Session,
):
    await app.db.validate_password(
        await app.db.user_get(session.snowflake), data.password
    )
    server = await app.db.server_get(await app.db.snowflake_get(server_snowflake))
    if str(server.owner.snowflake) != str(session.snowflake):
        raise Primitive.Error("You are not the owner of this server!", 403)
    return (
        await app.db.channel_remove(
            await app.db.channel_get(await app.db.snowflake_get(channel_snowflake))
        ),
        200,
    )


@bp.put("/<server_snowflake>/<channel_snowflake>/edit")
@tag(["Channels", "Editing"])
@auth()
@validate_request(Primitive.Update.Channel)
@validate_response(Primitive.Channel, 200)
async def channel_edit(
    server_snowflake: str,
    channel_snowflake: str,
    data: Primitive.Update.Channel,
    session: Primitive.Session,
):
    server = await app.db.server_get(await app.db.snowflake_get(server_snowflake))
    if str(server.owner.snowflake) != str(session.snowflake):
        raise Primitive.Error("You are not the owner of this server!", 403)
    return await app.db.channel_update(
        await app.db.channel_get(await app.db.snowflake_get(channel_snowflake)),
        name=data.name,
        picture_url=data.picture,
    )


@bp.put("/<channel_snowflake>/messages")
@tag(["Channels", "Messages", "Creation"])
@auth()
@validate_request(Primitive.Create.Message)
@validate_response(Primitive.Message, 200)
async def channel_message_make(
    channel_snowflake: str, data: Primitive.Create.Message, session: Primitive.Session
):
    # if channel is in user's channels create message
    user_channels = [
        str(x.snowflake)
        for x in (
            await app.db.user_list_channels(await app.db.user_get(session.snowflake))
        ).channels
    ]
    if channel_snowflake not in user_channels:
        raise Primitive.Error("Channel not found", 404)
    return await app.db.message_create(
        channel=await app.db.channel_get(await app.db.snowflake_get(channel_snowflake)),
        content=data.content,
        author=await app.db.user_get(session.snowflake),
    )


@bp.get("/<channel_snowflake>/messages")
@tag(["Channels", "Messages", "Listing"])
@auth()
@validate_response(Primitive.List.Messages, 200)
@validate_querystring(Primitive.Option.MessagesQuery)
async def channel_message_list(
    channel_snowflake: str,
    session: Primitive.Session,
    query_args: Primitive.Option.MessagesQuery,
):
    user_channels = [
        str(x.snowflake)
        for x in (
            await app.db.user_list_channels(await app.db.user_get(session.snowflake))
        ).channels
    ]
    if query_args.before is not None:
        msg = await app.db.message_get(await app.db.snowflake_get(query_args.before))
        if str(msg.channel.snowflake) != channel_snowflake:
            raise Primitive.Error("Before message not found", 404)

    if channel_snowflake not in user_channels:
        raise Primitive.Error("Channel not found", 404)
    response = await app.db.channel_list_messages(
        await app.db.channel_get(await app.db.snowflake_get(channel_snowflake)),
        limit=query_args.limit,
        before=int(query_args.before) if query_args.before is not None else None,
    )
    return response, 200


@bp.delete("/<channel_snowflake>/messages/<message_snowflake>")
@tag(["Channels", "Messages", "Deletion"])
@auth()
@validate_response(Primitive.Response.Success, 200)
async def channel_message_delete(
    channel_snowflake: str,
    message_snowflake: str,
    session: Primitive.Session,
):
    user_channels = [
        str(x.snowflake)
        for x in (
            await app.db.user_list_channels(await app.db.user_get(session.snowflake))
        ).channels
    ]
    if channel_snowflake not in user_channels:
        raise Primitive.Error("Channel not found", 404)
    await app.db.message_remove(
        await app.db.message_get(await app.db.snowflake_get(message_snowflake))
    )
    return (Primitive.Response.Success(response="Successfully removed message"), 200)
