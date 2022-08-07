import codecs
from dataclasses import dataclass
import zlib
import bcrypt
from quart import Blueprint
from quart import current_app as app
from quart_schema import tag, validate_headers, validate_request, validate_response

from common.primitive import Primitive
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


class Registration:
    @dataclass
    class Data:
        username: str
        password: str

    Success = Primitive.Snowflake
    Failure = Primitive.Error
    InputError = Primitive.Error


@bp.put("/register")
@tag(["Authorization", "Creation"])
@validate_request(Registration.Data)
@validate_response(Registration.Success, 201)
@validate_response(Registration.Failure, 409)
@validate_response(Registration.InputError, 400)
async def auth_register(data: Registration.Data):
    r = validate_string(data.username, minlength=3)
    if r is not None:
        return Registration.InputError(r), 400
    r = validate_string(data.password)
    if r is not None:
        return Registration.InputError(r), 400

    try:
        snowflake = await app.db.fetch_val(
            f"""INSERT INTO users (snowflake, username, passwordhash) VALUES (:snowflake, :username, :passwordhash) RETURNING snowflake""",
            values={
                "snowflake": next(app.snowflake_gen),
                "username": f"{data.username}",
                "passwordhash": zlib.compress(
                    bcrypt.hashpw(
                        codecs.encode(data.password, "utf-8"), bcrypt.gensalt()
                    )
                ),
            },
        )
    except Exception as e:
        return Registration.Failure(f"""User already exists"""), 409
    return Registration.Success(str(snowflake)), 201


class Login:
    @dataclass
    class Data:
        username: str
        password: str
        session_name: str

    Success = Primitive.Token
    InputError = Primitive.Error
    Failure = Primitive.Error
    NotExist = Primitive.Error
    Ratelimited = Primitive.Error


@bp.post("/login")
@tag(["Authorization"])
@validate_request(Login.Data)
@validate_response(Login.Success, 201)
@validate_response(Login.Failure, 401)
@validate_response(Login.NotExist, 404)
@validate_response(Login.Ratelimited, 429)
@validate_response(Login.InputError, 400)
async def auth_login(data: Login.Data):
    ratelimit = 300
    ratecount = 1
    r = validate_string(data.username, minlength=3)
    if r is not None:
        return Login.InputError(r)
    r = validate_string(data.password)
    if r is not None:
        return Login.InputError(r)
    r = validate_string(data.session_name, minlength=1, maxlength=100)
    if r is not None:
        return Login.InputError(r)
    d = await _fetch_user_data(
        app.db, username=data.username, field="(passwordhash, snowflake)"
    )

    if d is Exception or d is None:
        return Login.NotExist("User does not exist"), 404

    (pw, snowflake) = d
    if not await _is_ratelimited(
        app.db, "/api/auth/login", ratelimit, ratecount, snowflake
    ):
        if bcrypt.checkpw(codecs.encode(data.password, "utf-8"), zlib.decompress(pw)):
            token = await _add_user_token(app, snowflake, data.session_name)
            return Login.Success(str(token)), 201
        return Login.Failure("Incorrect password"), 401
    else:
        return (
            Login.Ratelimited(
                f"You can only use this endpoint {ratecount} time(s) every {ratelimit} seconds"
            ),
            429,
        )


class Logout:
    Success = Primitive.GenericStr
    Headers = Primitive.TokenHeader
    Failure = Primitive.Error


@bp.delete("/logout")
@tag(["Authorization"])
@validate_response(Logout.Success, 201)
@validate_response(Logout.Failure, 401)
@validate_headers(Logout.Headers)
async def auth_logout(headers: Logout.Headers):
    response = await _remove_user_token(app.db, headers.x_token)
    if response is not None:
        return (
            Logout.Success(f"Successfully invalidated token for session {response}"),
            201,
        )
    else:
        return Logout.Failure(f"Token does not exist"), 401


class Sessions:
    Headers = Primitive.TokenHeader
    SessionsList = Primitive.GenericList
    Failure = Primitive.Error


@bp.get("/sessions")
@tag(["Info"])
@validate_headers(Sessions.Headers)
@validate_response(Sessions.SessionsList, 200)
@validate_response(Sessions.Failure, 401)
async def auth_sessions(headers: Sessions.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    if snowflake is not None:
        tokenlist = await _get_all_tokens(app.db, snowflake)
        return Sessions.SessionsList(tokenlist), 200
    else:
        return Sessions.Failure("Invalid token"), 401


class DeleteAccount:
    Headers = Primitive.TokenHeader

    @dataclass
    class Data:
        password: str

    Unauthorized = Primitive.Error
    NotExist = Primitive.Error
    Success = Primitive.GenericStr


@bp.delete("/remove_account_yes_im_serous_wa_wa_we_wa")
@tag(["Authorization"])
@validate_headers(DeleteAccount.Headers)
@validate_request(DeleteAccount.Data)
@validate_response(DeleteAccount.Unauthorized, 401)
@validate_response(DeleteAccount.Success, 204)
@validate_response(DeleteAccount.NotExist, 404)
async def auth_remove(data: DeleteAccount.Data, headers: DeleteAccount.Headers):
    snowflake = await _get_snowflake_from_token(app.db, headers.x_token)
    pw = await _fetch_user_data(
        app.db,
        snowflake=snowflake,
        field="passwordhash",
    )
    if pw is Exception or pw is None:
        return DeleteAccount.NotExist("User does not exist"), 404

    if bcrypt.checkpw(codecs.encode(data.password, "utf-8"), zlib.decompress(pw)):
        await _delete_user(app.db, snowflake)
        return DeleteAccount.Success("Dont let the door hit you on the way out"), 201
    return DeleteAccount.Unauthorized("Incorrect password"), 401
