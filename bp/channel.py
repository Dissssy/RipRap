import codecs
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
from common.db import (
    _add_channel_to_server,
    _create_message,
    _delete_channel,
    _fetch_user_data,
    _get_channel_info,
    _get_channel_messages,
    _get_channel_users,
    _get_snowflake_from_token,
    _get_user_tokens,
    _grant_channel_access,
    _has_access_to_channel,
    _is_owner,
)

import common.primitive as Primitive
from common.utils import validate_snowflake, validate_string

bp = Blueprint("channel", __name__)


@bp.put("/<server_snowflake>/create")
@tag(["Channels", "Servers", "Creation"])
@validate_headers(Primitive.Header.Token)
@validate_request(Primitive.Create.Channel)
@validate_response(Primitive.Channel, 200)
@validate_response(Primitive.Error.InvalidInput, 400)
@validate_response(Primitive.Error.Unauthorized, 401)
async def channel_make(
    server_snowflake: str,
    data: Primitive.Create.Channel,
    headers: Primitive.Header.Token,
):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        response = await _is_owner(app.db, server_snowflake, snowflake)
        if type(response) is not str:
            url = ""
            if data.picture_url is not None:
                url = data.picture_url
            r = validate_string(url, minlength=0, maxlength=100)
            if r is not None:
                return Primitive.Error.InvalidInput(r), 400
            r = validate_string(data.name, minlength=1, maxlength=100)
            if r is not None:
                return Primitive.Error.InvalidInput(r), 400
            resp = await app.db.execute(
                f"""INSERT INTO channels (snowflake, picture, name) VALUES (:snowflake, :picture, :name) RETURNING (snowflake, picture, name)""",
                values={
                    "snowflake": next(app.snowflake_gen),
                    "picture": url,
                    "name": data.name,
                },
            )
            channel_dict = {
                "snowflake": str(resp[0]),
                "picture": resp[1],
                "name": resp[2],
            }
            await _add_channel_to_server(
                app.db, server_snowflake, channel_dict["snowflake"]
            )
            await _grant_channel_access(app.db, channel_dict["snowflake"], snowflake)
            return (
                cast(Primitive.Channel, channel_dict),
                200,
            )
        else:
            return Primitive.Error.Unauthorized(response), 401
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


@bp.get("/<channel_snowflake>")
@tag(["Channels", "Info"])
@validate_headers(Primitive.Header.Token)
@validate_response(Primitive.Channel, 200)
@validate_response(Primitive.Error.Unauthorized, 401)
async def channel_info(channel_snowflake: str, headers: Primitive.Header.Token):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if await _has_access_to_channel(app.db, channel_snowflake, snowflake):
            info = await _get_channel_info(app.db, channel_snowflake)
            if info is None:
                return
            return (
                cast(Primitive.Channel, info),
                200,
            )
        else:
            return (
                Primitive.Error.Unauthorized("You do not have access to this channel"),
                401,
            )
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


@bp.delete("/<server_snowflake>/<channel_snowflake>")
@tag(["Channels"])
@validate_headers(Primitive.Header.Token)
@validate_request(Primitive.Option.Password)
@validate_response(Primitive.Error.Unauthorized, 401)
@validate_response(Primitive.Response.Success, 204)
async def channel_delete(
    server_snowflake: str,
    channel_snowflake: str,
    data: Primitive.Option.Password,
    headers: Primitive.Header.Token,
):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if await _has_access_to_channel(app.db, channel_snowflake, snowflake):
            pw = await _fetch_user_data(
                app.db,
                snowflake=snowflake,
                field="passwordhash",
            )
            if bcrypt.checkpw(
                codecs.encode(data.password, "utf-8"), zlib.decompress(pw)
            ):
                response = await _delete_channel(
                    app.db, channel_snowflake, server_snowflake, snowflake
                )
                if type(response) == str:
                    return Primitive.Error.Unauthorized(response), 401
                return Primitive.Response.Success(f"Channel successfully deleted"), 201
            return Primitive.Error.Unauthorized("Incorrect password"), 401
        else:
            return (
                Primitive.Error.Unauthorized("You do not have access to this channel"),
                401,
            )
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


@bp.put("/<channel_snowflake>/messages")
@tag(["Channels", "Creation"])
@validate_headers(Primitive.Header.Token)
@validate_request(Primitive.Create.Message)
@validate_response(Primitive.Message, 200)
@validate_response(Primitive.Error.Unauthorized, 401)
@validate_response(Primitive.Error.InvalidInput, 400)
async def channel_create_message(
    channel_snowflake: str,
    data: Primitive.Create.Message,
    headers: Primitive.Header.Token,
):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if await _has_access_to_channel(app.db, channel_snowflake, snowflake):
            resp = validate_string(data.content, 1, 2000)
            if resp is None:
                msg = await _create_message(
                    app, channel_snowflake, snowflake, data.content
                )
                sendmsg = msg.copy()
                sendmsg["channel_snowflake"] = channel_snowflake
                channelusers = await _get_channel_users(app.db, channel_snowflake)
                for channeluser in channelusers:
                    usertokens = await _get_user_tokens(app.db, channeluser)
                    for usertoken in usertokens:
                        if app.ws.get(usertoken, None) is not None:
                            app.ws[usertoken].append({"code": 100, "data": sendmsg})
                return cast(Primitive.Message, msg)
            else:
                return Primitive.Error.InvalidInput(resp)
        else:
            return (
                Primitive.Error.Unauthorized("You do not have access to this channel"),
                401,
            )
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


@bp.get("/<channel_snowflake>/messages")
@tag(["Channels", "Info"])
@validate_headers(Primitive.Header.Token)
@validate_querystring(Primitive.Option.MessagesQuery)
@validate_response(Primitive.List.Messages, 200)
@validate_response(Primitive.Error.Unauthorized, 401)
@validate_response(Primitive.Error.InvalidSnowflake, 400)
@validate_response(Primitive.Error.InvalidInput, 400)
async def channel_get_messages(
    channel_snowflake: str,
    headers: Primitive.Header.Token,
    query_args: Primitive.Option.MessagesQuery,
):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if validate_snowflake(channel_snowflake):
            if await _has_access_to_channel(app.db, channel_snowflake, snowflake):
                messages = await _get_channel_messages(
                    app.db, channel_snowflake, query_args.limit, query_args.before
                )
                if type(messages) == str:
                    return Primitive.Error.InvalidInput(messages), 400
                else:
                    pass
                    return Primitive.List.Messages(messages), 200
            else:
                return (
                    Primitive.Error.Unauthorized(
                        "You do not have access to this channel"
                    ),
                    401,
                )
        else:
            return (
                Primitive.Error.InvalidSnowflake(f"{channel_snowflake} is invalid"),
                400,
            )
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401
