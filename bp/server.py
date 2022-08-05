import codecs
from dataclasses import dataclass
from typing import Optional, TypedDict
import zlib
import bcrypt
from quart import Blueprint
from quart import current_app as app
from quart_schema import tag, validate_headers, validate_request, validate_response
from common.db import (
    _delete_server,
    _fetch_user_data,
    _get_server_info,
    _get_snowflake_from_token,
    _get_user_servers,
    _grant_server_access,
    _has_access_to_server,
)

from common.primitive import Primitive
from common.utils import validate_string

bp = Blueprint("server", __name__)


class Servers:
    Headers = Primitive.TokenHeader

    Servers = Primitive.GenericList
    Unauthorized = Primitive.Error


@bp.get("/list")
@tag(["Servers", "Info"])
@validate_headers(Servers.Headers)
@validate_response(Servers.Servers, 200)
@validate_response(Servers.Unauthorized, 401)
async def server_userlist(headers: Servers.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        return Servers.Servers(await _get_user_servers(app.db, snowflake)), 200
    else:
        return Servers.Unauthorized("Token is invalid"), 401


class MakeServer:
    Headers = Primitive.TokenHeader

    @dataclass
    class Data:
        name: str
        picture_url: Optional[str]

    Success = Primitive.Snowflake
    InputError = Primitive.Error
    Unauthorized = Primitive.Error


@bp.put("/create")
@tag(["Servers", "Creation"])
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
                "snowflake": next(app.snowflake_gen),
                "picture": url,
                "owner_snowflake": int(snowflake),
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
@tag(["Servers", "Info"])
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


class DeleteServer:
    Headers = Primitive.TokenHeader

    @dataclass
    class Data:
        password: str

    Unauthorized = Primitive.Error
    NotExist = Primitive.Error
    Success = Primitive.GenericStr


@bp.delete("/<server_snowflake>")
@tag(["Servers"])
@validate_headers(DeleteServer.Headers)
@validate_request(DeleteServer.Data)
@validate_response(DeleteServer.Unauthorized, 401)
@validate_response(DeleteServer.Success, 204)
async def server_delete(
    server_snowflake: str, data: DeleteServer.Data, headers: DeleteServer.Headers
):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if await _has_access_to_server(app.db, server_snowflake, snowflake):
            pw = await _fetch_user_data(
                app.db,
                snowflake=snowflake,
                field="passwordhash",
            )
            if bcrypt.checkpw(
                codecs.encode(data.password, "utf-8"), zlib.decompress(pw)
            ):
                response = await _delete_server(app.db, server_snowflake, snowflake)
                if type(response) == str:
                    return DeleteServer.Unauthorized(response), 401
                return DeleteServer.Success(f"Server successfully deleted"), 201
            return DeleteServer.Unauthorized("Incorrect password"), 401
        else:
            return (
                DeleteServer.Unauthorized("You do not have access to this server"),
                401,
            )
    else:
        return DeleteServer.Unauthorized("Token is invalid"), 401
