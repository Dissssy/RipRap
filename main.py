from dataclasses import dataclass
import sys
from typing import Optional, TypedDict

from quart_cors import cors

sys.path.append(".")

import asyncio
import zlib
from quart import Quart, websocket
from quart_schema import (
    QuartSchema,
    validate_headers,
    validate_response,
)
from snowflake import SnowflakeGenerator
import json
import uuid

import config

import common.primitive as Primitive
from common.db import _create_db_connection, _get_snowflake_from_token

import bp.auth, bp.server, bp.channel, bp.user

app = Quart(__name__)
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


@app.route("/api", strict_slashes=False)
async def server_info():
    return {"Version": 1.0}


def register_blueprints(app: Quart):
    blueprints = [bp.auth.bp, bp.server.bp, bp.channel.bp, bp.user.bp]
    for blueprint in blueprints:
        app.register_blueprint(blueprint, url_prefix=f"/api/{blueprint.name}")


register_blueprints(app)


def encode_json(thing) -> bytes:
    return zlib.compress(bytes(json.dumps(thing), "utf-8"))


def decode_json(nibble: bytes):
    return json.loads(zlib.decompress(nibble).decode("utf-8"))


# @app.route("/")
# async def index():
#     count_users = await app.db.fetch_val("SELECT COUNT(*) FROM users")
#     return f"There are {count_users} users registered!"


@app.before_serving
async def startup() -> None:
    app.db = await _create_db_connection()
    app.snowflake_gen = SnowflakeGenerator(0)
    app.uuid = uuid.uuid1
    # set up as {"snowflake": [ list of websockets ]}
    app.ws = {}


@app.after_serving
async def shutdown() -> None:
    pass


class WebSocket:
    Response = TypedDict("websocket_tx", {"code": int, "data": Optional[dict]})


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
                data = await websocket.receive_json()
                match data.get("code", None):
                    case 1:
                        self.lasthb = None
                    case 2:
                        penis = data.get("data", None)
                        if penis is not None:
                            self.token = penis.get("token", None)
                            if self.token is not None:
                                snowflake = await _get_snowflake_from_token(
                                    app.db, self.token
                                )
                                if snowflake is not None:
                                    app.ws[self.token] = []
                                else:
                                    print(self.token)
                    case _:
                        print(data)
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


@app.cli.command("init_db")
def init_db() -> None:
    async def _inner() -> None:
        db = await _create_db_connection()
        async with await app.open_resource("schema.sql", "r") as file:
            for query in (await file.read()).split(";"):
                await db.fetch_val(f"{query};")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_inner())


if __name__ == "__main__":
    app.run("0.0.0.0", 14500)
