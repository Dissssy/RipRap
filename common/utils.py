# goodchars = (
#     "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.<>[]1234567890-=!@#$%^&*()_+"
# )

import asyncio
from functools import wraps
from hashlib import sha512
from typing import Callable

import quart_schema

import common.primitive as Primitive
from quart import current_app as app


def validate_string(string: str, minlength=8, maxlength=48):
    if string == "string":
        return
    # r = re.search(r"(?![A-Za-z0-9._=!@#$%^&*()+-])", string, re.RegexFlag.I)
    # r = None
    # for char in string:
    #     if char not in goodchars:
    #         r = char
    #         break
    # if r is not None:
    #     return f"{string} contains invalid characters ({r})! Can only be comprised of these characters: {goodchars}"
    if len(string) < minlength:
        raise Primitive.Error(
            f"{string} too short! Should be at least {minlength} characters!", 400
        )
    if len(string) > maxlength:
        raise Primitive.Error(
            f"{string} too long! Should be at most {maxlength} characters!", 400
        )


def validate_snowflake(snowflake: str) -> bool:
    try:
        x = int(snowflake)
        return True
    except:
        return False


def twofellas(snowflakeone: str, snowflaketwo: str) -> str:
    if int(snowflakeone) > int(snowflaketwo):
        return snowflakeone + snowflaketwo


# def auth(*args, **kwargs):
#
#     async def wrapper(func):


#     return wrapper


def auth(keep_token=False):
    def decorator(func):
        @quart_schema.validate_headers(Primitive.Header.Token)
        @wraps(func)
        async def wrapper(*args, **kwargs):
            headers: Primitive.Header.Token = kwargs["headers"]
            if not keep_token:
                kwargs.pop("headers")
            session: Primitive.Session = await app.db.session_get(headers.x_token)
            if session is None:
                raise Primitive.Error("Token is invalid", 401)
            kwargs["session"] = session
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def ratelimit(time: int, quantity: int = 1):
    def decorator(func: Callable):
        @auth()
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not await app.db.ratelimited_get(
                func.__name__, kwargs["session"], time, quantity
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def cache(time: int = None):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nocache = False
            if kwargs.get("nocache") is not None:
                nocache = kwargs.pop("nocache")
            if not nocache:
                cachehash = ""
                for arg in args:
                    if isinstance(arg, str):
                        cachehash += arg
                    elif isinstance(arg, int):
                        cachehash += str(arg)
                    elif isinstance(arg, Primitive.Snowflake):
                        cachehash += str(arg.snowflake)

                cachehash = sha512(cachehash.encode("utf-8")).hexdigest()

                if app.cache.get(func.__name__) is None:
                    app.cache[func.__name__] = {}
                if app.cache[func.__name__].get(cachehash) is None:
                    app.cache[func.__name__][cachehash] = await func(*args, **kwargs)
                else:
                    # run get_updated_cache in a seperate thread
                    # print("Updating cache")
                    asyncio.create_task(get_updated_cache(func, cachehash, args, kwargs))
            return app.cache[func.__name__][cachehash]

        return wrapper

    return decorator


async def get_updated_cache(func, cachehash, args, kwargs):
    if app.cache.get(func.__name__) is None:
        app.cache[func.__name__] = {}
    app.cache[func.__name__][cachehash] = await func(*args, **kwargs)
    # print("Updated cache")
