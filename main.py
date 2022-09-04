import sys
from typing import Any, Optional, TypedDict
import asyncpg
from colorama import Fore
import prisma

from quart_cors import cors
import quart_schema
import globals

sys.path.append(".")

import asyncio
from quart import Quart, websocket
from quart_schema import (
    QuartSchema,
)

import common.primitive as Primitive

import config

from common.db import RIPRAPDatabase

import bp.auth, bp.server, bp.channel, bp.user

globals.initialize()

app = Quart(__name__)
# app.debug = True
QuartSchema(
    app,
    swagger_ui_path="/api/docs",
    openapi_path="/api/openapi.json",
    redoc_ui_path="/api/redocs",
)
app.config.update(
    {
        "DATABASE_URL": config.DATABASE_URL,
        "SMTP": {
            "SERVER": config.SMTP_SERVER,
            "PORT": config.SMTP_PORT,
            "USER": config.SMTP_USER,
            "PASSWORD": config.SMTP_PASSWORD,
        },
    }
)
app = cors(app, allow_origin="*")
app.db: RIPRAPDatabase = RIPRAPDatabase(config.DATABASE_URL)


@app.route("/api", strict_slashes=False)
async def server_info():
    return {"Version": 1.0}


def register_blueprints(app: Quart):
    blueprints = [bp.auth.bp, bp.user.bp, bp.server.bp, bp.channel.bp]
    for blueprint in blueprints:
        app.register_blueprint(blueprint, url_prefix=f"/api/{blueprint.name}")


register_blueprints(app)


# def encode_json(thing) -> bytes:
#     return zlib.compress(bytes(json.dumps(thing), "utf-8"))


# def decode_json(nibble: bytes):
#     return json.loads(zlib.decompress(nibble).decode("utf-8"))


# @app.route("/")
# async def index():
#     count_users = await app.db.fetch_val("SELECT COUNT(*) FROM users")
#     return f"There are {count_users} users registered!"


@app.before_serving
async def startup() -> None:
    app.db = RIPRAPDatabase(config.DATABASE_URL)
    await app.db._connect()
    # set up as {"snowflake": [ list of websockets ]}
    app.ws = {}
    app.cache = {}
    app.loader = __loader__.name
    app.loader = "benchmark"
    # app.websocket_handlers = utils.websocket_handlers
    # await app.db._cleanup_db()
    if app.loader == "__main__":
        await test()


@app.after_serving
async def shutdown() -> None:
    pass


class WebSocket:
    Response = TypedDict("websocket_tx", {"code": int, "data": Optional[dict]})


@app.errorhandler(Primitive.Error)
async def handle_notexist_session(error: Primitive.Error):
    return {"error": error.args[0]}, error.args[1]


@app.errorhandler(asyncpg.exceptions.UniqueViolationError)
async def handle_unique_violation(error: asyncpg.exceptions.UniqueViolationError):
    return {"error": str(error)}, 400


@app.errorhandler(prisma.errors.UniqueViolationError)
async def handle_unique_violation(error: prisma.errors.UniqueViolationError):
    return {"error": str(error)}, 400


@app.errorhandler(quart_schema.validation.ResponseSchemaValidationError)
async def handle_schema_validation(
    error: quart_schema.validation.ResponseSchemaValidationError,
):
    return {"error": str(error.__dict__) + ", tell @Dissy#2112 he's an idiot"}, 400


@app.errorhandler(ConnectionAbortedError)
async def handle_connection_aborted(error: ConnectionAbortedError):
    return {"error": str(error)}, 400


# def recursivedir(class_, depth=0):
#     outstring = ""
#     if isinstance(class_, str):
#         return class_
#     if hasattr(class_, "__name__"):
#         return class_.__name__
#     if depth > 25:
#         return "..."
#     for attr in dir(class_):
#         outstring += f"{attr}: [{recursivedir(getattr(class_, attr), depth + 1)}], "
#     #     if not attr.startswith("__") and not attr.startswith("_"):
#     #         if getattr(getattr(class_, attr), "__str__") is not None:
#     #             if not getattr(class_, attr).__str__().startswith("<"):
#     #                 outstring += f"{attr}: {getattr(class_, attr).__str__()}, "
#     #             else:
#     #                 outstring += (
#     #                     f"{attr}: [{recursivedir(getattr(class_, attr), depth + 1)}], "
#     #                 )
#     #         else:
#     #             outstring += (
#     #                 f"{attr}: [{recursivedir(getattr(class_, attr), depth + 1)}], "
#     #             )
#     print(outstring)
#     return outstring


# @app.websocket("/ws")
# async def ws():
#     while True:
#         data = await websocket.receive()
#         print(data)
#         await websocket.send(data)

eventspersecond = 10
heartbeattime = 30

# websocket docs
# 0 is auth code
# -1 is error
# 1 is heartbeat
# 1xx is creation events
# 100 is message create
# 2xx is updat events
# 200 is be message update
# 201 is user update
# 3xx is deletion events
# 300 is message delete

# x00 is message
# x01 is user
# x02 is server
# x03 is channel


class WebSocketClient:
    def __init__(self):
        self.hbcount = 0
        self.lasthb = None
        self.missed = 0
        self.error = False
        self.token = None

    async def TX(self):
        i = 0
        while not self.error:
            await asyncio.sleep(1.0 / eventspersecond)
            i = (i + 1) % (eventspersecond * heartbeattime)
            try:
                if i == 1:
                    if self.lasthb is not None:
                        self.missed += 1
                        if self.missed > 1:
                            raise asyncio.CancelledError
                    else:
                        self.missed = 0
                    await websocket.send_json(
                        WebSocket.Response({"code": 1, "data": {"hb": self.hbcount}})
                    )
                    self.lasthb = self.hbcount
                    self.hbcount += 1

                if self.token is not None:
                    while len(app.ws[self.token]) > 0:
                        await websocket.send_json(
                            WebSocket.Response(app.ws[self.token].pop(0))
                        )
            except Exception as e:
                print(e)
                if self.token is not None:
                    app.ws.pop(self.token)
                self.error = True
                raise

    async def RX(self):
        while not self.error:
            try:
                data: dict[str, str | dict] = await websocket.receive_json()
                match data.get("code", None):
                    case 1:
                        self.lasthb = None
                    case 2:
                        thisdata = data.get("data", None)
                        if thisdata is not None:
                            self.token = thisdata.get("token", None)
                            if self.token is not None:
                                session = app.db.session_get(self.token)
                                if session is not None:
                                    app.ws[self.token] = []
                                else:
                                    print(self.token)
                    case _:
                        thisdata = data.get("data", None)
                        if thisdata is not None:
                            if self.token is not None:
                                session = app.db.session_get(self.token)
                                if session is not None:
                                    if data["code"] in globals.websocket_handlers:
                                        try:
                                            app.ws[self.token].append(
                                                {
                                                    "code": data["code"],
                                                    "data": await globals.websocket_handlers[
                                                        data["code"]
                                                    ](
                                                        session, **thisdata
                                                    ),
                                                }
                                            )
                                        except Exception as e:
                                            app.ws[self.token].append(
                                                {"code": -1, "data": {"Error": str(e)}}
                                            )
                                else:
                                    print(self.token)

            except Exception as e:
                print(e)
                if self.token is not None:
                    app.ws.pop(self.token)
                self.error = True
                raise


@app.websocket("/ws")
async def ws():
    webthighighs = WebSocketClient()
    producer = asyncio.create_task(webthighighs.TX())
    consumer = asyncio.create_task(webthighighs.RX())
    await asyncio.gather(producer, consumer)
    producer.set_exception(asyncio.CancelledError)
    consumer.set_exception(asyncio.CancelledError)
    del webthighighs
    # websocket.headers
    # await websocket.send_json(WebSocket.Response({"code": 0}))
    # rx = await websocket.receive_json()
    # token = await websocket.receive_json()["token"]
    # snowflake = await _get_snowflake_from_token(app.db, token)
    # if snowflake is not None:
    #     app.ws[token] = []
    #     i = 0
    #     hbv = 0
    #     while True:
    #         await asyncio.sleep(1.0 / eventspersecond)
    #         i = (i + 1) % (eventspersecond * heartbeattime)
    #         try:
    #             if i == 0:
    #                 await websocket.send_json(
    #                     WebSocket.Response({"code": 1, "data": {"hb": hbv}})
    #                 )
    #                 hbv += 1
    #             while len(app.ws[token]) > 0:
    #                 await websocket.send_json(WebSocket.Response(app.ws[token].pop(0)))
    #         except asyncio.CancelledError:
    #             await websocket.close()
    #             app.ws.pop(token)
    #             return
    # else:
    #     await websocket.send_json(
    #         WebSocket.Response({"code": -1, "data": {"Error": "Invalid token"}})
    #     )
    #     await websocket.close()
    #     return
    # print(websocket.headers)
    # snowflake = _get_snowflake_from_token(app.db, websocket.headers.x_token)
    # print(snowflake)
    # if snowflake is not None:
    #     while True:
    #         await asyncio.sleep(1.0)
    #         try:
    #             await websocket.send(
    #                 WebSocket.Response({"opcode": "1", "data": {"beep"}})
    #             )
    #         except asyncio.CancelledError:
    #             # Handle disconnect
    #             raise
    # else:
    #     await websocket.send(
    #         WebSocket.Response({"opcode": "0", "data": {"Error": "Invalid token"}})
    #     )


async def test():
    print(Fore.BLUE + "Cleaning up database")
    await app.db._db.user.delete(where={"email": "test@test.test"})
    await app.db._db.user.delete(where={"email": "test2@test2.test2"})
    print(Fore.BLUE + "Beginning tests")
    nocachestring = Fore.YELLOW + "NOCACHE         | "
    failure = False
    try:
        await app.db.user_set(name="test", password="test", email="test")
    except:
        failure = True
    assert failure is True
    print(Fore.BLUE + "Email failure test passed")
    testsetuser = await app.db.user_set(
        name="test", password="test", email="test@test.test"
    )
    print(Fore.BLUE + "User set test passed")
    assert (
        await app.db.user_get(snowflake=testsetuser.snowflake)
    ).snowflake == testsetuser.snowflake
    print(Fore.BLUE + "User gotten from snowflake")
    assert (
        await app.db.user_get(email="test@test.test")
    ).snowflake == testsetuser.snowflake
    print(Fore.BLUE + "User gotten from email")
    assert (
        await app.db.user_set(
            snowflake=testsetuser.snowflake,
            name="test2",
            email="test2@test2.test2",
            password="test",
            newpassword="test2",
        )
    ).snowflake == testsetuser.snowflake
    print(Fore.BLUE + "User update test passed")
    await app.db.user_get(snowflake=testsetuser.snowflake)
    assert (await app.db.user_get(snowflake=testsetuser.snowflake)).name == "test2"
    print(Fore.BLUE + "User name update test passed")
    session = await app.db.session_set(
        email="test2@test2.test2", session_name="test_session", password="test2"
    )
    assert session.user is not None
    print(Fore.BLUE + "User exists within Session test passed")
    session = await app.db.session_get(token=session.token)
    assert session.user is not None
    print(Fore.BLUE + "User exists within gotten Session test passed")
    server = await app.db.server_set(user=testsetuser, name="test")
    assert server.name == "test"
    print(Fore.BLUE + "Server set test passed")
    assert server.owner.snowflake == testsetuser.snowflake
    print(Fore.BLUE + "Server owner test passed")
    assert server.members[0].snowflake == testsetuser.snowflake
    print(Fore.BLUE + "Server member test passed")
    server = await app.db.server_set(
        snowflake=server.snowflake, name="test2", user=testsetuser
    )
    assert server.name == "test2"
    print(Fore.BLUE + "Server update test passed")
    channel = await app.db.channel_set(user=testsetuser, name="test", server=server)
    assert channel.name == "test"
    print(Fore.BLUE + "Channel set test passed")
    # await asyncio.sleep(1)
    server = await app.db.server_get(snowflake=server.snowflake, user=testsetuser)
    server = await app.db.server_get(snowflake=server.snowflake, user=testsetuser)
    assert server.channels[0].snowflake == channel.snowflake
    print(Fore.BLUE + "Channel get from server test passed")
    channel = await app.db.channel_set(
        user=testsetuser, snowflake=channel.snowflake, name="test2", server=server
    )
    assert channel.name == "test2"
    print(Fore.BLUE + "Channel update test passed")
    message = await app.db.message_set(
        channel=channel, user=testsetuser, content="test"
    )
    assert message.content == "test"
    print(Fore.BLUE + "Message set test passed")
    message = (await app.db.message_get(channel=channel))[0]
    assert message.content == "test"
    print(Fore.BLUE + "Message get test passed")
    message = await app.db.message_set(
        channel=channel, snowflake=message.snowflake, content="test2", user=testsetuser
    )
    assert message.content == "test2"
    print(Fore.BLUE + "Message edit test passed")
    # await asyncio.sleep(1)
    messages = await app.db.message_get(channel=channel)
    messages = await app.db.message_get(channel=channel)
    assert messages[0].content == "test2"
    print(Fore.BLUE + "Message get edited test passed")
    assert len(messages) == 1
    print(Fore.BLUE + "Message get all test passed")
    await app.db.message_set(
        channel=channel, snowflake=message.snowflake, delete=True, user=testsetuser
    )
    messages = await app.db.message_get(channel=channel)
    assert len(messages) == 0
    print(Fore.BLUE + "Message delete test passed")

    for i in range(0, 11):
        await app.db.message_set(channel=channel, user=testsetuser, content=str(i))
    messages = await app.db.message_get(channel=channel)
    assert len(messages) == 10
    print(Fore.BLUE + "Message get 10 test passed")
    channel = await app.db.channel_get(
        channel_snowflake=channel.snowflake, user=testsetuser
    )
    channel = await app.db.channel_get(
        channel_snowflake=channel.snowflake, user=testsetuser
    )
    assert channel.message_count == 11
    print(Fore.BLUE + "Channel message count test passed")

    oldchannel = channel.snowflake
    channel = await app.db.channel_set(
        user=testsetuser, snowflake=oldchannel, delete=True, server=server
    )
    assert channel is None
    print(Fore.BLUE + "Channel delete test passed")
    failure = False
    try:
        await app.db.channel_get(snowflake=oldchannel, user=testsetuser)
    except:
        failure = True
    assert failure is True
    print(Fore.BLUE + "Channel was deleted test passed")
    oldsnowflake = server.snowflake
    server = await app.db.server_set(
        snowflake=server.snowflake, delete=True, user=testsetuser
    )
    assert server is None
    print(Fore.BLUE + "Server delete test passed")
    failure = False
    try:
        await app.db.server_get(snowflake=oldsnowflake, user=testsetuser)
    except:
        failure = True
    assert failure is True
    print(Fore.BLUE + "Server was deleted test passed")
    assert (
        await app.db.user_set(
            snowflake=testsetuser.snowflake, delete=True, password="test2"
        )
    ).email != "test2@test2.test2"
    print(Fore.BLUE + "User delete test passed")
    assert (await app.db.user_get(snowflake=testsetuser.snowflake)) is not None
    print(Fore.BLUE + "User was deleted then recreated test passed")

    print(Fore.GREEN + "All tests passed")
    await app.db._db.user.delete(where={"snowflake": testsetuser.snowflake})
    print(Fore.GREEN + "Test user was cleaned up")
    # print(app.cache)


# @app.cli.command()
# def test() -> None:
#     async def _inner() -> None:
#         app.db = RIPRAPDatabase(config.DATABASE_URL)
#         await app.db._connect()


#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(_inner())


if __name__ == "__main__":
    # app.run("0.0.0.0", 14500)
    app.run(use_reloader=False)
