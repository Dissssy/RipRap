import asyncio
from quart import Blueprint
from quart import current_app as app
from quart_schema import tag, validate_request, validate_response, validate_querystring
from common.primitive import Channel, Create, List, Message, Option, Response, Session
from common.utils import auth, benchmark, send_to_websocket

bp = Blueprint("message", __name__)

# GET /<channel_snowflake>/?limit=x&before=x (list all messages in channel if user is in server)
#     200 OK - Returns list of all messages
#     401 Unauthorized - Token invalid
#     404 Not Found - Server or channel not found
#     500 Internal Server Error


@bp.get("/<channel_snowflake>/")
@tag(["Message", "Info"])
@benchmark()
@auth()
@validate_querystring(Option.MessagesQuery)
@validate_response(List.Messages, 200)
async def message_list(
    session: Session, channel_snowflake: str, query_args: Option.MessagesQuery
) -> List.Messages:
    """Get list of up to 100 messages in a channel (optionally before a specific message)."""
    return List.Messages(
        messages=(
            await app.db.message_get(
                channel=await app.db.channel_get(
                    channel_snowflake=channel_snowflake, user=session.user
                ),
                # user=session.user,
                limit=query_args.limit,
                before=query_args.before,
            )
        )
    )


# # GET /<server_snowflake>/<channel_snowflake>/<message_snowflake>/ (message info if message exists and user is in server)
# #     200 OK - Returns message object
# #     401 Unauthorized - Token invalid
# #     404 Not Found - Server, channel or message not found
# #     500 Internal Server Error


# @bp.get("/<server_snowflake>/<channel_snowflake>/<message_snowflake>/")
# @tag(["Message", "Info", "Authed"])


# PUT /<server_snowflake>/<channel_snowflake>/ (create message if user is in server)
#     201 Created - Message created - returns message object
#     401 Unauthorized - Token invalid
#     404 Not Found - Server or channel not found
#     400 Bad Request - Input error
#     500 Internal Server Error


@bp.put("/<channel_snowflake>/")
@tag(["Message", "Create"])
@benchmark()
@auth()
@validate_request(Create.Message)
@validate_response(Message, 201)
async def message_create(
    session: Session, channel_snowflake: str, data: Create.Message
) -> Message:
    """Create a message in a channel."""
    channel: Channel = await app.db.channel_get(
        channel_snowflake=channel_snowflake, user=session.user, includeserver=True
    )
    try:
        members = [x.snowflake for x in channel.server.members]
    except:
        channel: Channel = await app.db.channel_get(
            channel_snowflake=channel_snowflake, user=session.user, includeserver=True
        )
        members = [x.snowflake for x in channel.server.members]
    message = await app.db.message_set(
        channel=channel,
        user=session.user,
        content=data.content,
    )
    asyncio.create_task(
        send_to_websocket(members, {"code": 100, "data": message.dict()})
    )
    return message


# DELETE /<server_snowflake>/<channel_snowflake>/<message_snowflake>/ (delete message if user is owner or message author)
#     200 OK - Message deleted - returns nothing
#     401 Unauthorized - Token invalid
#     404 Not Found - Server, channel or message not found
#     500 Internal Server Error


@bp.delete("/<channel_snowflake>/<message_snowflake>/")
@tag(["Message", "Delete"])
@benchmark()
@auth()
async def message_delete(
    session: Session, channel_snowflake: str, message_snowflake: str
) -> Response.Success:
    """Delete a message in a channel."""
    channel: Channel = await app.db.channel_get(
        channel_snowflake=channel_snowflake, user=session.user, includeserver=True
    )
    try:
        members = [x.snowflake for x in channel.server.members]
    except:
        channel: Channel = await app.db.channel_get(
            channel_snowflake=channel_snowflake, user=session.user, includeserver=True
        )
        members = [x.snowflake for x in channel.server.members]
    await app.db.message_set(
        channel=channel,
        snowflake=message_snowflake,
        user=session.user,
        delete=True,
    )
    asyncio.create_task(
        send_to_websocket(
            members,
            {
                "code": 300,
                "data": {"snowflake": message_snowflake, "channel": channel.dict()},
            },
        )
    )
    return Response.Success(response="Message deleted")


@bp.patch("/<channel_snowflake>/<message_snowflake>/")
@tag(["Message", "Update"])
@benchmark()
@auth()
@validate_request(Create.Message)
@validate_response(Message, 200)
async def message_update(
    session: Session,
    channel_snowflake: str,
    message_snowflake: str,
    data: Create.Message,
) -> Message:
    """Update a message in a channel."""
    channel: Channel = await app.db.channel_get(
        channel_snowflake=channel_snowflake, user=session.user, includeserver=True
    )
    try:
        members = [x.snowflake for x in channel.server.members]
    except:
        channel: Channel = await app.db.channel_get(
            channel_snowflake=channel_snowflake, user=session.user, includeserver=True
        )
        members = [x.snowflake for x in channel.server.members]
    message = await app.db.message_set(
        channel=channel,
        snowflake=message_snowflake,
        user=session.user,
        content=data.content,
    )

    asyncio.create_task(
        send_to_websocket(members, {"code": 200, "data": message.dict()})
    )
    return message
