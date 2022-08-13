import codecs
import zlib
import bcrypt
from quart import Blueprint
from quart import current_app as app


from quart_schema import tag, validate_headers, validate_request, validate_response
from common.db import RIPRAPDatabase

import common.primitive as Primitive
from common.utils import auth, ratelimit, validate_string

bp = Blueprint("auth", __name__)


@bp.put("/register")
@tag(["Auth", "Creation"])
@validate_request(Primitive.Create.User)
@validate_response(Primitive.User, 201)
@validate_response(Primitive.Response.InputError, 400)
async def auth_register(data: Primitive.Create.User):
    r = validate_string(data.username, minlength=3, maxlength=32)
    if r is not None:
        return Primitive.Response.InputError(response=r), 400
    r = validate_string(data.password, minlength=8, maxlength=128)
    if r is not None:
        return Primitive.Response.InputError(response=r), 400
    return (
        await app.db.user_create(
            data.username, data.nickname, data.picture, data.password
        )
    ).dict()


@bp.post("/login")
@tag(["Auth", "Creation"])
@validate_request(Primitive.Create.Session)
@validate_response(Primitive.Session, 201)
async def auth_login(data: Primitive.Create.Session):
    #     ratelimit = 300
    #     ratecount = 1
    r = validate_string(data.username, minlength=3)
    if r is not None:
        raise Primitive.Error(r, 400)
    r = validate_string(data.password)
    if r is not None:
        raise Primitive.Error(r, 400)
    r = validate_string(data.session_name, minlength=1, maxlength=100)
    if r is not None:
        raise Primitive.Error(r, 400)
    d: Primitive.User = await app.db.user_get(username=data.username, internal=True)

    if bcrypt.checkpw(
        codecs.encode(data.password, "utf-8"), zlib.decompress(d.passwordhash)
    ):
        return await app.db.session_create(d.snowflake, data.session_name), 201
    raise Primitive.Error("Incorrect password", 401)


@bp.delete("/logout")
@tag(["Auth", "Deletion"])
@validate_response(Primitive.Response.Success, 201)
@validate_headers(Primitive.Header.Token)
async def auth_logout(headers: Primitive.Header.Token):
    response = await app.db.session_remove(headers.x_token)
    return (
        Primitive.Response.Success(
            response=f"Successfully invalidated token for session {response}"
        ),
        201,
    )


@bp.get("/sessions")
@tag(["Auth", "Info"])
@auth()
@validate_response(Primitive.List.Sessions, 200)
async def auth_sessions(session: Primitive.Session):
    return (
        await app.db.session_list(session.snowflake),
        200,
    )


@bp.delete("/remove_account_yes_im_serous_wa_wa_we_wa")
@tag(["Auth", "Deletion"])
@validate_request(Primitive.Option.Password)
@validate_response(Primitive.Response.Success, 204)
@auth()
async def auth_remove(data: Primitive.Option.Password, session: Primitive.Session):
    d: Primitive.User = await app.db.user_get(
        snowflake=session.snowflake, internal=True
    )
    if bcrypt.checkpw(
        codecs.encode(data.password, "utf-8"), zlib.decompress(d.passwordhash)
    ):
        await app.db.user_remove(d)
        for wssnowflake in app.ws:
            app.ws[wssnowflake].append({"code": "201", "data": d})
        return (
            Primitive.Response.Success(
                response="Dont let the door hit you on the way out"
            ),
            201,
        )
    else:
        raise Primitive.Error("Incorrect password", 401)
