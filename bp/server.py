import codecs
from typing import cast
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
    _get_user_info,
    _get_user_servers,
    _grant_server_access,
    _has_access_to_server,
)

import common.primitive as Primitive
from common.utils import validate_string

bp = Blueprint("server", __name__)


@bp.get("/list")
@tag(["Servers", "Info"])
@validate_headers(Primitive.Header.Token)
@validate_response(Primitive.List.Servers, 200)
@validate_response(Primitive.Error.Unauthorized, 401)
async def server_userlist(headers: Primitive.Header.Token):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        return (
            Primitive.List.Servers(servers=await _get_user_servers(app.db, snowflake)),
            200,
        )
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


@bp.put("/create")
@tag(["Servers", "Creation"])
@validate_headers(Primitive.Header.Token)
@validate_request(Primitive.Create.Server)
@validate_response(Primitive.Server, 200)
@validate_response(Primitive.Error.InvalidInput, 400)
@validate_response(Primitive.Error.Unauthorized, 401)
async def server_make(data: Primitive.Create.Server, headers: Primitive.Header.Token):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
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
            f"""INSERT INTO servers (snowflake, picture, owner_snowflake, name) VALUES (:snowflake, :picture, :owner_snowflake, :name) RETURNING (snowflake, picture, owner_snowflake, name)""",
            values={
                "snowflake": next(app.snowflake_gen),
                "picture": url,
                "owner_snowflake": int(snowflake),
                "name": data.name,
            },
        )
        server_dict = {
            "snowflake": str(resp[0]),
            "picture": resp[1],
            "owner": _get_user_info(app.db, resp[2]),
            "name": resp[3],
        }
        await _grant_server_access(app.db, server_dict["snowflake"], snowflake)
        return (
            cast(Primitive.Server, server_dict),
            200,
        )

    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


@bp.get("/<server_snowflake>")
@tag(["Servers", "Info"])
@validate_headers(Primitive.Header.Token)
@validate_response(Primitive.Server, 200)
@validate_response(Primitive.Error.Unauthorized, 401)
async def server_info(server_snowflake: str, headers: Primitive.Header.Token):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        if await _has_access_to_server(app.db, server_snowflake, snowflake):
            return (
                cast(
                    Primitive.Server, await _get_server_info(app.db, server_snowflake)
                ),
                200,
            )
        else:
            return (
                Primitive.Error.Unauthorized("You do not have access to this server"),
                401,
            )
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401


@bp.delete("/<server_snowflake>")
@tag(["Servers"])
@validate_headers(Primitive.Header.Token)
@validate_request(Primitive.Option.Password)
@validate_response(Primitive.Error.Unauthorized, 401)
@validate_response(Primitive.Response.Success, 200)
async def server_delete(
    server_snowflake: str,
    data: Primitive.Option.Password,
    headers: Primitive.Header.Token,
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
                    return Primitive.Error.Unauthorized(response), 401
                return Primitive.Response.Success(f"Server successfully deleted"), 200
            return Primitive.Error.Unauthorized("Incorrect password"), 401
        else:
            return (
                Primitive.Error.Unauthorized("You do not have access to this server"),
                401,
            )
    else:
        return Primitive.Error.Unauthorized("Token is invalid"), 401
