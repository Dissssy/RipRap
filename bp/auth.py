import codecs
from dataclasses import asdict, dataclass
import zlib
import bcrypt
from quart import Blueprint
from quart import current_app as app
from quart_schema import validate_headers, validate_request, validate_response

from common.primitive import Primitive
from common.utils import validate_string
from common.db import (
    _fetch_user_data,
    _get_all_tokens,
    _get_snowflake_from_token,
    _is_ratelimited,
    _add_user_token,
    _remove_user_token,
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
@validate_request(Registration.Data)
@validate_response(Registration.Success, 201)
@validate_response(Registration.Failure, 409)
@validate_response(Registration.InputError, 400)
async def register_handler(data: Registration.Data):
    dayta = asdict(data)
    r = validate_string(dayta["username"], minlength=3)
    if r is not None:
        return Registration.InputError(r)
    r = validate_string(dayta["password"])
    if r is not None:
        return Registration.InputError(r)

    try:
        snowflake = await app.db.fetch_val(
            f"""INSERT INTO users (snowflake, username, passwordhash) VALUES (:snowflake, :username, :passwordhash) RETURNING snowflake""",
            values={
                "snowflake": f"{next(app.snowflake_gen)}",
                "username": f'{dayta["username"]}',
                "passwordhash": zlib.compress(
                    bcrypt.hashpw(
                        codecs.encode(dayta["password"], "utf-8"), bcrypt.gensalt()
                    )
                ),
            },
        )
    except:
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
@validate_request(Login.Data)
@validate_response(Login.Success, 201)
@validate_response(Login.Failure, 401)
@validate_response(Login.NotExist, 404)
@validate_response(Login.Ratelimited, 429)
async def auth_login(data: Login.Data):
    ratelimit = 300
    ratecount = 1
    dayta = asdict(data)
    r = validate_string(dayta["username"], minlength=3)
    if r is not None:
        return Login.InputError(r)
    r = validate_string(dayta["password"])
    if r is not None:
        return Login.InputError(r)
    r = validate_string(dayta["session_name"], minlength=1, maxlength=100)
    if r is not None:
        return Login.InputError(r)
    d = await _fetch_user_data(
        app, username=dayta["username"], field="(passwordhash, snowflake)"
    )
    if d is Exception:
        return Login.NotExist("User does not exist!", 404)
    if d is None:
        return Login.NotExist("User does not exist!", 404)
    (pw, snowflake) = d
    if not await _is_ratelimited(
        app, "/api/auth/login", ratelimit, ratecount, snowflake
    ):
        if bcrypt.checkpw(
            codecs.encode(dayta["password"], "utf-8"), zlib.decompress(pw)
        ):
            # snowflake = await _fetch_user_data(username)
            token = await _add_user_token(app, snowflake, dayta["session_name"])
            return Login.Success(str(token)), 201
        return Login.Failure("Incorrect password"), 401
    else:
        return (
            Login.Ratelimited(
                f"You can only use this endpoint {ratecount} time(s) every {ratelimit} seconds!"
            ),
            429,
        )


class Logout:
    Success = Primitive.GenericStr
    Headers = Primitive.TokenHeader
    Failure = Primitive.Error


@bp.delete("/logout")
@validate_response(Logout.Success, 201)
@validate_response(Logout.Failure, 401)
@validate_headers(Logout.Headers)
async def auth_logout(headers: Logout.Headers):
    response = await _remove_user_token(app, headers.x_token)
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
@validate_headers(Sessions.Headers)
@validate_response(Sessions.SessionsList, 200)
@validate_response(Sessions.Failure, 401)
async def auth_sessions(headers: Sessions.Headers):
    snowflake = await _get_snowflake_from_token(app, headers.x_token)
    if snowflake is not None:
        tokenlist = await _get_all_tokens(app, snowflake)
        return Sessions.SessionsList(tokenlist)
    else:
        return Sessions.Failure("Invalid token!")
