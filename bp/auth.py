import codecs
from dataclasses import dataclass
from typing import cast
import zlib
import bcrypt
from quart import Blueprint
from quart import current_app as app
from quart_schema import tag, validate_headers, validate_request, validate_response

import common.primitive as Primitive
from common.utils import validate_string
from common.db import (
    _fetch_user_data,
    _get_all_tokens,
    _get_snowflake_from_token,
    _is_ratelimited,
    _add_user_token,
    _remove_user_token,
    _delete_user,
)

bp = Blueprint("auth", __name__)


@bp.put("/register")
@tag(["Authorization", "Creation"])
@validate_request(Primitive.Create.User)
@validate_response(Primitive.User, 201)
@validate_response(Primitive.Error.AlreadyExists, 409)
@validate_response(Primitive.Error.InvalidInput, 400)
async def auth_register(data: Primitive.Create.User):
    r = validate_string(data.username, minlength=3)
    if r is not None:
        return Primitive.Error.InvalidInput(r), 400
    r = validate_string(data.password)
    if r is not None:
        return Primitive.Error.InvalidInput(r), 400

    try:
        userinfo = await app.db.fetch_val(
            f"""INSERT INTO users (snowflake, username, passwordhash, nickname, picture) VALUES (:snowflake, :username, :passwordhash, :nickname, :picture) RETURNING (snowflake, username, nickname, picture)""",
            values={
                "snowflake": next(app.snowflake_gen),
                "username": f"{data.username}",
                "passwordhash": zlib.compress(
                    bcrypt.hashpw(
                        codecs.encode(data.password, "utf-8"), bcrypt.gensalt()
                    )
                ),
                "nickname": data.nickname,
                "picture": data.picture,
            },
        )
    except Exception as e:
        return Primitive.Error.AlreadyExists(f"""User already exists"""), 409
    return (
        Primitive.User(
            snowflake=str(userinfo[0]),
            username=userinfo[1],
            nickname=userinfo[2],
            picture=userinfo[3],
        ),
        201,
    )


@bp.post("/login")
@tag(["Authorization"])
@validate_request(Primitive.Create.Token)
@validate_response(Primitive.Session, 201)
@validate_response(Primitive.Error.Unauthorized, 401)
@validate_response(Primitive.Error.DoesNotExist, 404)
@validate_response(Primitive.Error.Ratelimited, 429)
@validate_response(Primitive.Error.InvalidInput, 400)
async def auth_login(data: Primitive.Create.Token):
    ratelimit = 300
    ratecount = 1
    r = validate_string(data.username, minlength=3)
    if r is not None:
        return Primitive.Error.InvalidInput(r), 400
    r = validate_string(data.password)
    if r is not None:
        return Primitive.Error.InvalidInput(r), 400
    r = validate_string(data.session_name, minlength=1, maxlength=100)
    if r is not None:
        return Primitive.Error.InvalidInput(r), 400
    d = await _fetch_user_data(
        app.db, username=data.username, field="(passwordhash, snowflake)"
    )

    if d is Exception or d is None:
        return Primitive.Error.DoesNotExist("User does not exist"), 404

    (pw, snowflake) = d
    ratelimitdata = await _is_ratelimited(
        app.db, "/api/auth/login", ratelimit, ratecount, snowflake
    )
    if ratelimitdata == 0:
        if bcrypt.checkpw(codecs.encode(data.password, "utf-8"), zlib.decompress(pw)):
            return (
                cast(
                    Primitive.Session,
                    await _add_user_token(app, snowflake, data.session_name),
                ),
                201,
            )
        return Primitive.Error.Unauthorized("Incorrect password"), 401
    else:
        return (
            Primitive.Error.Ratelimited(
                f"You can only use this endpoint {ratecount} time(s) every {ratelimit} seconds",
                ratelimitdata,
            ),
            429,
        )


@bp.delete("/logout")
@tag(["Authorization"])
@validate_response(Primitive.Response.Success, 201)
@validate_response(Primitive.Error.DoesNotExist, 401)
@validate_headers(Primitive.Header.Token)
async def auth_logout(headers: Primitive.Header.Token):
    response = await _remove_user_token(app.db, headers.x_token)
    if response is not None:
        return (
            Primitive.Response.Success(
                f"Successfully invalidated token for session {response}"
            ),
            201,
        )
    else:
        return Primitive.Error.DoesNotExist(f"Token does not exist"), 401


@bp.get("/sessions")
@tag(["Info"])
@validate_headers(Primitive.Header.Token)
@validate_response(Primitive.List.Sessions, 200)
@validate_response(Primitive.Error.Unauthorized, 401)
async def auth_sessions(headers: Primitive.Header.Token):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        return Primitive.List.Sessions(await _get_all_tokens(app.db, snowflake)), 200
    else:
        return Primitive.Error.Unauthorized("Invalid token"), 401


@bp.delete("/remove_account_yes_im_serous_wa_wa_we_wa")
@tag(["Authorization"])
@validate_headers(Primitive.Header.Token)
@validate_request(Primitive.Option.Password)
@validate_response(Primitive.Error.Unauthorized, 401)
@validate_response(Primitive.Response.Success, 204)
@validate_response(Primitive.Error.DoesNotExist, 404)
async def auth_remove(data: Primitive.Option.Password, headers: Primitive.Header.Token):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        pw = await _fetch_user_data(
            app.db,
            snowflake=snowflake,
            field="passwordhash",
        )
        if pw is Exception or pw is None:
            return Primitive.Error.DoesNotExist("User does not exist"), 404

        if bcrypt.checkpw(codecs.encode(data.password, "utf-8"), zlib.decompress(pw)):
            await _delete_user(app, snowflake)
            userinfo = await _fetch_user_data(snowflake)
            for wssnowflake in app.ws:
                app.ws[wssnowflake].append({"code": "201", "data": userinfo})
            return (
                Primitive.Response.Success("Dont let the door hit you on the way out"),
                201,
            )
        return Primitive.Error.Unauthorized("Incorrect password"), 401
    else:
        return Primitive.Error.Unauthorized("Invalid token"), 401
