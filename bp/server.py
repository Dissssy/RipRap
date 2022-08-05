import codecs
from dataclasses import dataclass
from typing import Optional
import zlib
import bcrypt
from quart import Blueprint
from quart import current_app as app
from quart_schema import tag, validate_headers, validate_request, validate_response
from common.db import (
    _get_server_info,
    _get_snowflake_from_token,
    _get_user_servers,
    _grant_server_access,
    _has_access_to_server,
)

from common.primitive import Primitive
from common.utils import validate_string

bp = Blueprint("servers", __name__)


class Servers:
    Headers = Primitive.TokenHeader
    Servers = Primitive.GenericList
    Unauthorized = Primitive.Error


@bp.get("/")
@tag(["V1", "Servers", "Info"])
@validate_headers(Servers.Headers)
@validate_response(Servers.Servers, 200)
@validate_response(Servers.Unauthorized, 401)
async def server_userlist(headers: Servers.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        return Servers.Servers(await _get_user_servers(app.db, snowflake)), 200
    else:
        return Servers.Unauthorized("Token is invalid"), 401
    # if pw is Exception or pw is None:
    #     return DeleteAccount.NotExist("User does not exist"), 404

    # if bcrypt.checkpw(codecs.encode(data.password, "utf-8"), zlib.decompress(pw)):
    #     await _delete_user(app.db, snowflake)
    #     return DeleteAccount.Success("Dont let the door hit you on the way out"), 201
    # return DeleteAccount.Unauthorized("Incorrect password"), 401


class MakeServer:
    Headers = Primitive.TokenHeader

    @dataclass
    class Data:
        name: str
        picture_url: Optional[str]

    Success = Primitive.Snowflake
    InputError = Primitive.Error
    Unauthorized = Primitive.Error


@bp.put("/")
@tag(["V1", "Servers"])
@validate_headers(MakeServer.Headers)
@validate_request(MakeServer.Data)
@validate_response(MakeServer.Success, 200)
@validate_response(MakeServer.InputError, 400)
@validate_response(MakeServer.Unauthorized, 401)
async def server_make(data: MakeServer.Data, headers: MakeServer.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        url = ""
        if data.picture_url is not None:
            url = data.picture_url
        r = validate_string(url, minlength=0, maxlength=100)
        if r is not None:
            return MakeServer.InputError(r)
        r = validate_string(data.name, minlength=1, maxlength=100)
        if r is not None:
            return MakeServer.InputError(r)
        server_snowflake = await app.db.execute(
            f"""INSERT INTO servers (snowflake, picture, owner_snowflake, name) VALUES (:snowflake, :picture, :owner_snowflake, :name) RETURNING snowflake""",
            values={
                "snowflake": f"{next(app.snowflake_gen)}",
                "picture": url,
                "owner_snowflake": snowflake,
                "name": data.name,
            },
        )
        return (
            MakeServer.Success(
                await _grant_server_access(app.db, server_snowflake, snowflake)
            ),
            200,
        )

    else:
        return MakeServer.Unauthorized("Token is invalid"), 401


class ServerInfo:
    Headers = Primitive.TokenHeader

    @dataclass
    class Info:
        name: str
        image: str
        owner: str
        snowflake: str
        channels: list[str]

    Unauthorized = Primitive.Error


@bp.get("/<server_snowflake>")
@tag(["V1", "Servers", "Info"])
@validate_headers(ServerInfo.Headers)
@validate_response(ServerInfo.Info, 200)
@validate_response(ServerInfo.Unauthorized, 401)
async def server_info(server_snowflake: str, headers: ServerInfo.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if await _has_access_to_server(app.db, server_snowflake, snowflake):
            info = await _get_server_info(app.db, server_snowflake)
            if info is None:
                return
            return (
                ServerInfo.Info(
                    info["name"],
                    info["picture"],
                    info["owner_snowflake"],
                    info["snowflake"],
                    info["channels"],
                ),
                200,
            )
        else:
            return ServerInfo.Unauthorized("You do not have access to this server"), 401
    else:
        return ServerInfo.Unauthorized("Token is invalid"), 401
