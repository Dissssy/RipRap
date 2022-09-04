# goodchars = (
#     "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.<>[]1234567890-=!@#$%^&*()_+"
# )

import globals

import asyncio
import inspect
import config
from functools import wraps
from hashlib import sha512
from pprint import pprint
from time import time as now
from typing import Callable, Optional
import quart
from colorama import Fore

import quart_schema

import common.primitive as Primitive
from quart import current_app as app

print(Fore.WHITE)


def validate_string(string: str, /, *, minlength=8, maxlength=48):
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
            session: Primitive.Session = await app.db.session_get(token=headers.x_token)
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


def async_cache(time: int = 300):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            before = now()
            # pprint(app.cache)
            nocache = False
            if kwargs.get("nocache") is not None:
                nocache = kwargs.pop("nocache")
            if not nocache:
                cachehash = "async"
                for arg in args:
                    try:
                        if "snowflake" in dir(arg):
                            cachehash = f"{cachehash}{arg.snowflake}"
                        else:
                            cachehash = f"{cachehash}{arg}"
                    except:
                        print(arg)
                    # if isinstance(arg, str):
                    #     cachehash += arg
                    # elif isinstance(arg, int):
                    #     cachehash += str(arg)
                    # elif isinstance(arg, Primitive.Snowflake):
                    #     cachehash += str(arg.snowflake)
                cachehash = sha512(cachehash.encode("utf-8")).hexdigest()
                if app.cache.get(func.__name__) is None:
                    app.cache[func.__name__] = {}
                if app.cache[func.__name__].get(cachehash) is None:
                    app.cache[func.__name__][cachehash] = [
                        await func(*args, **kwargs),
                        0,
                    ]
                else:
                    if app.cache[func.__name__][cachehash][1] > now():
                        asyncio.create_task(
                            get_updated_async_cache(func, cachehash, time, args, kwargs)
                        )
                        if app.loader == "__main__":
                            stringy = f"CACHED   {(now()) - before:.4f} "
                            # stringy += " " * (17 - len(stringy))
                            stringy += "| "
                            print(Fore.GREEN + stringy, end="\n" + Fore.GREEN)
                        return app.cache[func.__name__][cachehash][0]
                    else:
                        app.cache[func.__name__][cachehash] = [
                            await func(*args, **kwargs),
                            now() + time,
                        ]
                if app.loader == "__main__":
                    stringy = f"UNCACHED {(now()) - before:.4f} "
                    # stringy += " " * (17 - len(stringy))
                    stringy += "| "
                    print(Fore.RED + stringy, end="\n" + Fore.RED)
                return app.cache[func.__name__][cachehash][0]
            else:
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def sync_cache(time: int = 300):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            before = now()
            # pprint(app.cache)
            nocache = False
            if kwargs.get("nocache") is not None:
                nocache = kwargs.pop("nocache")
            # if not nocache:
            cachehash = "sync"
            arglist = []
            for arg in args:
                arglist.append(arg)
            for arg in kwargs:
                arglist.append(kwargs[arg])
            newarglist = []
            for arg in arglist:
                newarg = ""
                try:
                    newarg = str(arg.snowflake)
                except:
                    try:
                        newarg = str(arg.token)
                    except:
                        # print(arg)
                        newarg = str(arg)
                newarglist.append(newarg)
            newarglist.sort()
            # for arg in arglist:
            #     try:
            #         # if "snowflake" in dir(arg):
            #         #     cachehash = f"{cachehash}{arg.snowflake}"
            #         # elif "user" in dir(arg):
            #         #     cachehash = f"{cachehash}{arg.user.snowflake}"
            #         # elif "server" in dir(arg):
            #         #     cachehash = f"{cachehash}{arg.server.snowflake}"
            #         # else:
            #         # add = str(arg)
            #         # try:
            #         #     add = arg.snowflake
            #         # except:
            #         #     try:
            #         #         add = arg.token
            #         #     except:
            #         #         print("WHY")
            #         # print("                                 " + add)
            #         cachehash = f"{cachehash}{add}"
            #     except Exception as e:
            #         print(e)
            #         print(arg)
            # if isinstance(arg, str):
            #     cachehash += arg
            # elif isinstance(arg, int):
            #     cachehash += str(arg)
            # elif isinstance(arg, Primitive.Snowflake):
            #     cachehash += str(arg.snowflake)
            cachehash = "sync" + "".join(newarglist)
            # print(cachehash)
            # print(f"{func.__name__}: {cachehash}")
            cachehash = sha512(cachehash.encode("utf-8")).hexdigest()

            if app.cache.get(func.__name__) is None:
                app.cache[func.__name__] = {}
            if app.cache[func.__name__].get(cachehash) is None:
                app.cache[func.__name__][cachehash] = [
                    func(*args, **kwargs),
                    0,
                ]
            else:
                if app.cache[func.__name__][cachehash][1] > now() and not nocache:
                    asyncio.create_task(
                        get_updated_sync_cache(func, cachehash, time, args, kwargs)
                    )
                    if app.loader == "__main__":
                        stringy = f"CACHED   {(now()) - before:.4f} "
                        # stringy += " " * (17 - len(stringy))
                        stringy += "| "
                        print(Fore.GREEN + stringy, end="\n" + Fore.GREEN)
                    return app.cache[func.__name__][cachehash][0]
                else:
                    app.cache[func.__name__][cachehash] = [
                        func(*args, **kwargs),
                        now() + time,
                    ]
            if app.loader == "__main__":
                stringy = f"UNCACHED {(now()) - before:.4f} "
                # stringy += " " * (17 - len(stringy))
                stringy += "| "
                print(Fore.RED + stringy, end="\n" + Fore.RED)
            return app.cache[func.__name__][cachehash][0]

        return wrapper

    return decorator


async def get_updated_async_cache(func, cachehash, time, args, kwargs):
    if app.cache.get(func.__name__) is None:
        app.cache[func.__name__] = {}
    app.cache[func.__name__][cachehash] = [await func(*args, **kwargs), now() + time]


async def get_updated_sync_cache(func, cachehash, time, args, kwargs):
    if app.cache.get(func.__name__) is None:
        app.cache[func.__name__] = {}
    app.cache[func.__name__][cachehash] = [func(*args, **kwargs), now() + time]


def benchmark():
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            before = now()
            result = func(*args, **kwargs)
            if inspect.iscoroutine(result):
                result = await result
            if app.loader == "benchmark":
                name = f"{func.__name__}: ".replace("_", " ").title()
                name += " " * (20 - len(name))
                print(
                    Fore.CYAN
                    + name
                    + Fore.MAGENTA
                    + f"{(now()) - before:.4f} "
                    + Fore.BLACK,
                    end="",
                )
            return result

        return wrapper

    return decorator


def websocket(code: int, data: dict = {}, sendto: Optional[str] = None):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if len(args) > 0:
                return {"code": -1, "data": {"Error": "Invalid arguments"}}
            for arg in kwargs.keys():
                if arg not in data:
                    return {"code": -1, "data": {"Error": "Invalid argument " + arg}}
            try:
                result = func(*args, **kwargs)
                if inspect.iscoroutine(result):
                    result = await result
            except Exception as e:
                return {"code": -1, "data": {"Error": str(e)}}
            if sendto is not None:
                if sendto == "all":
                    for token in app.ws.keys():
                        await app.ws[token].append({"code": code, "data": result})
                # elif sendto == "servermembers":
                #     for token in app.ws.keys():
                #         thisuser = await app.db.user_get(
                #             snowflake=(await app.db.session_get(token=token)), level=0
                #         )
                #         if thisuser.servers is not None:
                #             for server in thisuser.servers:
                #                 if server.snowflake == kwargs.get("server_id"):
                #                     usersessions = await app.db.session_get(
                #                         token=token, listall=True
                #                     )
                #                     await app.ws[token].append(
                #                         {"code": code, "data": result}
                #                     )

            return {"code": code, "data": result}

        globals.websocket_handlers[code] = wrapper
        return func

    return decorator
