import codecs
from dataclasses import asdict, dataclass
from typing import Optional, TypedDict
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
    _get_user_channels,
    _get_user_tokens,
    _grant_channel_access,
    _has_access_to_channel,
    _is_owner,
)

from common.primitive import Primitive
from common.utils import validate_snowflake, validate_string

bp = Blueprint("channel", __name__)


# class Channels:
#     Headers = Primitive.TokenHeader
#     Channels = Primitive.GenericList
#     Unauthorized = Primitive.Error


# @bp.get("/list")
# @tag(["Channels", "Info"])
# @validate_headers(Channels.Headers)
# @validate_response(Channels.Channels, 200)
# @validate_response(Channels.Unauthorized, 401)
# async def channel_userlist(headers: Channels.Headers):
#     snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
#     if snowflake is not None:
#         return Channels.Channels(await _get_user_channels(app.db, snowflake)), 200
#     else:
#         return Channels.Unauthorized("Token is invalid"), 401


class MakeChannel:
    Headers = Primitive.TokenHeader

    @dataclass
    class Data:
        name: str
        picture_url: Optional[str]

    Success = Primitive.Snowflake
    InputError = Primitive.Error
    Unauthorized = Primitive.Error


@bp.put("/<server_snowflake>/create")
@tag(["Channels", "Servers", "Creation"])
@validate_headers(MakeChannel.Headers)
@validate_request(MakeChannel.Data)
@validate_response(MakeChannel.Success, 200)
@validate_response(MakeChannel.InputError, 400)
@validate_response(MakeChannel.Unauthorized, 401)
async def channel_make(
    server_snowflake: str, data: MakeChannel.Data, headers: MakeChannel.Headers
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
                return MakeChannel.InputError(r)
            r = validate_string(data.name, minlength=1, maxlength=100)
            if r is not None:
                return MakeChannel.InputError(r)
            channel_snowflake = await app.db.execute(
                f"""INSERT INTO channels (snowflake, picture, name) VALUES (:snowflake, :picture, :name) RETURNING snowflake""",
                values={
                    "snowflake": next(app.snowflake_gen),
                    "picture": url,
                    "name": data.name,
                },
            )
            await _add_channel_to_server(app.db, server_snowflake, channel_snowflake)
            return (
                MakeChannel.Success(
                    await _grant_channel_access(app.db, channel_snowflake, snowflake)
                ),
                200,
            )
        else:
            return MakeChannel.Unauthorized(response), 401
    else:
        return MakeChannel.Unauthorized("Token is invalid"), 401


class ChannelInfo:
    Headers = Primitive.TokenHeader

    @dataclass
    class Info:
        info: TypedDict(
            "Channel",
            {
                "name": str,
                "picture": Optional[str],
                "snowflake": str,
                "message_count": int,
            },
        )

    Unauthorized = Primitive.Error


@bp.get("/<channel_snowflake>")
@tag(["Channels", "Info"])
@validate_headers(ChannelInfo.Headers)
@validate_response(ChannelInfo.Info, 200)
@validate_response(ChannelInfo.Unauthorized, 401)
async def channel_info(channel_snowflake: str, headers: ChannelInfo.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if await _has_access_to_channel(app.db, channel_snowflake, snowflake):
            info = await _get_channel_info(app.db, channel_snowflake)
            if info is None:
                return
            return (
                ChannelInfo.Info(info),
                200,
            )
        else:
            return (
                ChannelInfo.Unauthorized("You do not have access to this channel"),
                401,
            )
    else:
        return ChannelInfo.Unauthorized("Token is invalid"), 401


class DeleteChannel:
    Headers = Primitive.TokenHeader

    @dataclass
    class Data:
        password: str

    Unauthorized = Primitive.Error
    NotExist = Primitive.Error
    Success = Primitive.GenericStr


@bp.delete("/<server_snowflake>/<channel_snowflake>")
@tag(["Channels"])
@validate_headers(DeleteChannel.Headers)
@validate_request(DeleteChannel.Data)
@validate_response(DeleteChannel.Unauthorized, 401)
@validate_response(DeleteChannel.Success, 204)
async def channel_delete(
    server_snowflake: str,
    channel_snowflake: str,
    data: DeleteChannel.Data,
    headers: DeleteChannel.Headers,
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
                    return DeleteChannel.Unauthorized(response), 401
                return DeleteChannel.Success(f"Channel successfully deleted"), 201
            return DeleteChannel.Unauthorized("Incorrect password"), 401
        else:
            return (
                DeleteChannel.Unauthorized("You do not have access to this channel"),
                401,
            )
    else:
        return DeleteChannel.Unauthorized("Token is invalid"), 401


class GetMessages:
    Headers = Primitive.TokenHeader

    @dataclass
    class Query:
        limit: Optional[int] = None
        before: Optional[str] = None

    @dataclass
    class Messages:
        messages: list[
            TypedDict(
                "Message",
                {
                    "content": str,
                    "author": TypedDict(
                        "User",
                        {
                            "snowflake": str,
                            "username": str,
                            "nickname": Optional[str],
                            "picture": Optional[str],
                        },
                    ),
                    "snowflake": str,
                },
            )
        ]

    Unauthorized = Primitive.Error
    Failure = Primitive.Error


@bp.get("/<channel_snowflake>/messages")
@tag(["Channels", "Info"])
@validate_headers(GetMessages.Headers)
@validate_querystring(GetMessages.Query)
@validate_response(GetMessages.Messages, 200)
@validate_response(GetMessages.Unauthorized, 401)
@validate_response(GetMessages.Failure, 400)
async def channel_get_messages(
    channel_snowflake: str, headers: GetMessages.Headers, query_args: GetMessages.Query
):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if channel_snowflake == "0":
        await _grant_channel_access(app.db, channel_snowflake, snowflake)
    if snowflake is not None:
        if validate_snowflake():
            if await _has_access_to_channel(app.db, channel_snowflake, snowflake):
                messages = await _get_channel_messages(
                    app.db, channel_snowflake, query_args.limit, query_args.before
                )
                if type(messages) == str:
                    return GetMessages.Failure(messages), 400
                else:
                    return GetMessages.Messages(messages), 200
            else:
                return (
                    GetMessages.Unauthorized("You do not have access to this channel"),
                    401,
                )
        else:
            return GetMessages.Failure(f"{channel_snowflake} is invalid"), 400
    else:
        return GetMessages.Unauthorized("Token is invalid"), 401


class CreateMessage:
    Headers = Primitive.TokenHeader

    @dataclass
    class Success:
        message: TypedDict(
            "Message",
            {
                "content": str,
                "author": TypedDict(
                    "User",
                    {
                        "snowflake": str,
                        "username": str,
                        "nickname": Optional[str],
                        "picture": Optional[str],
                    },
                ),
                "snowflake": str,
            },
        )

    Unauthorized = Primitive.Error

    @dataclass
    class Data:
        content: str

    Failure = Primitive.Error


@bp.put("/<channel_snowflake>/messages")
@tag(["Channels", "Creation"])
@validate_headers(CreateMessage.Headers)
@validate_request(CreateMessage.Data)
@validate_response(CreateMessage.Success, 200)
@validate_response(CreateMessage.Unauthorized, 401)
@validate_response(CreateMessage.Failure, 400)
async def channel_create_message(
    channel_snowflake: str, data: CreateMessage.Data, headers: CreateMessage.Headers
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
                return CreateMessage.Success(msg)
            else:
                return CreateMessage.Failure(resp)
        else:
            return (
                CreateMessage.Unauthorized("You do not have access to this channel"),
                401,
            )
    else:
        return CreateMessage.Unauthorized("Token is invalid"), 401
