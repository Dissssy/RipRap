import codecs
from typing import cast
import zlib
import bcrypt
from quart import Blueprint
from quart import current_app as app
from quart_schema import tag, validate_request, validate_response
import common.primitive as Primitive
from common.utils import auth, validate_string

bp = Blueprint("server", __name__)


@bp.get("/list")
@tag(["Servers", "Info", "Listing"])
@validate_response(Primitive.List.Servers, 200)
@auth()
async def server_userlist(session: Primitive.Session):
    return await app.db.user_list_servers(user=session.snowflake), 200


@bp.put("/create")
@tag(["Servers", "Creation"])
@auth()
@validate_request(Primitive.Create.Server)
@validate_response(Primitive.Server, 200)
async def server_make(data: Primitive.Create.Server, session: Primitive.Session):
    validate_string(data.name, minlength=1, maxlength=100)
    if data.picture_url is not None:
        validate_string(data.picture_url, minlength=1, maxlength=100)
    return await app.db.server_create(
        await app.db.user_get(session.snowflake), data.name, data.picture_url
    )


@bp.get("/<server_snowflake>")
@tag(["Servers", "Info"])
@auth()
@validate_response(Primitive.Server, 200)
async def server_info(server_snowflake: str, session: Primitive.Session):
    user_servers = [
        str(x.snowflake)
        for x in (
            await app.db.user_list_servers(await app.db.user_get(session.snowflake))
        ).servers
    ]
    if server_snowflake not in user_servers:
        raise Primitive.Error("Server not found", 404)
    return await app.db.server_get(await app.db.snowflake_get(server_snowflake)), 200


@bp.delete("/<server_snowflake>")
@tag(["Servers", "Deletion"])
@auth()
@validate_request(Primitive.Option.Password)
@validate_response(Primitive.Response.Success, 200)
async def server_delete(
    server_snowflake: str,
    data: Primitive.Option.Password,
    session: Primitive.Session,
):
    await app.db.validate_password(
        await app.db.user_get(session.snowflake, nocache=True), data.password
    )
    user_servers = {}
    for x in (
        await app.db.user_list_servers(await app.db.user_get(session.snowflake))
    ).servers:
        user_servers[str(x.snowflake)] = str(x.owner.snowflake)
    if server_snowflake not in user_servers.keys():
        raise Primitive.Error("Server not found", 404)
    if user_servers[str(x.snowflake)] != str(session.snowflake):
        raise Primitive.Error("You are not the owner of this server", 403)
    await app.db.server_remove(await app.db.snowflake_get(server_snowflake))
    return Primitive.Response.Success(response="Server deleted"), 200
