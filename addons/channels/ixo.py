import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Text

import rasa.core.channels.channel
from rasa.core.channels.channel import InputChannel, OutputChannel, UserMessage
import rasa.shared.utils.io
from sanic import Blueprint, response, Sanic
from sanic.request import Request
from sanic.response import HTTPResponse
from socketio import AsyncServer
from time import sleep
import json
logger = logging.getLogger(__name__)

DEFAULT_DELAY_IN_MESSAGES = 2 # seconds

class SocketBlueprint(Blueprint):
    def __init__(
        self, sio: AsyncServer, socketio_path: Text, *args: Any, **kwargs: Any
    ) -> None:
        """Creates a :class:`sanic.Blueprint` for routing socketio connenctions.

        :param sio: Instance of :class:`socketio.AsyncServer` class
        :param socketio_path: string indicating the route to accept requests on.
        """
        super().__init__(*args, **kwargs)
        self.ctx.sio = sio
        self.ctx.socketio_path = socketio_path


    def register(self, app: Sanic, options: Dict[Text, Any]) -> None:
        """Attach the Socket.IO webserver to the given Sanic instance.

        :param app: Instance of :class:`sanic.app.Sanic` class
        :param options: Options to be used while registering the
            blueprint into the app.
        """
        self.ctx.sio.attach(app, self.ctx.socketio_path)
        super().register(app, options)


class IxoOutput(OutputChannel):
    @classmethod
    def name(cls) -> Text:
        return "ixo"

    def __init__(self, sio: AsyncServer, bot_message_evt: Text, message_delay: int) -> None:
        self.sio = sio
        self.bot_message_evt = bot_message_evt
        self.message_delay = message_delay
        
    async def sleep(self, idx, response_len) -> None:

        logger.info(f"Sleeping for {self.message_delay} seconds")
        for i in range(self.message_delay):
            logger.info(f"Sleep : {i+1}")
            sleep(1)

    async def send_response(self, recipient_id: Text, message: Dict[Text, Any]) -> None:
        """Send a message to the client."""
        
        responses = []
        
        if message.get("quick_replies"):
            responses.append("quick_replies")
        
        elif message.get("buttons"):
            responses.append("buttons")
        
        elif message.get("text"):
            responses.append("text")
        
        if message.get("custom"):
            responses.append("custom")
        
        if message.get("image"):
            responses.append("image")
        
        if message.get("attachment"):
            responses.append("attachment")
        
        if message.get("elements"):
            responses.append("elements")
        
        logger.info(f"Sending message to {recipient_id}: {message}, responses: {responses}")

        responses_len = len(responses)
        
        for idx, response in enumerate(responses):
            
            if response == "quick_replies":
                
                await self.send_quick_replies(
                    recipient_id,
                    message.pop("text"),
                    message.pop("quick_replies"),
                    **message,
                )
                await self.sleep(idx, responses_len)
                
            if response == "buttons":
                
                await self.send_text_with_buttons(
                    recipient_id, message.pop("text"), message.pop("buttons"), **message
                )
                await self.sleep(idx, responses_len)
            
            if response == "text":
                
                await self.send_text_message(recipient_id, message.pop("text"), **message)
                await self.sleep(idx, responses_len)
                
            if response == "custom":
                
                await self.send_custom_json(recipient_id, message.pop("custom"), **message)
                await self.sleep(idx, responses_len)
                
            if response == "image":
                
                await self.send_image_url(recipient_id, message.pop("image"), **message)
                await self.sleep(idx, responses_len)
                
            if response == "attachment":
                
                await self.send_attachment(recipient_id, message.pop("attachment"), **message)
                await self.sleep(idx, responses_len)
                
            if response == "elements":
                
                await self.send_elements(recipient_id, message.pop("elements"), **message)
                await self.sleep(idx, responses_len)
            
    async def _send_message(self, socket_id: Text, response: Any) -> None:
        """Sends a message to the recipient using the bot event."""

        await self.sio.emit(self.bot_message_evt, response, room=socket_id)

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        """Send a message through this channel."""

        for message_part in text.strip().split("\n\n"):
            await self._send_message(recipient_id, {"text": message_part})

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any
    ) -> None:
        """Sends an image to the output"""

        message = {"attachment": {"type": "image", "payload": {"src": image}}}
        await self._send_message(recipient_id, message)

    async def send_text_with_buttons(
        self,
        recipient_id: Text,
        text: Text,
        buttons: List[Dict[Text, Any]],
        **kwargs: Any,
    ) -> None:
        """Sends buttons to the output."""

        # split text and create a message for each text fragment
        # the `or` makes sure there is at least one message we can attach the quick
        # replies to
        message_parts = text.strip().split("\n\n") or [text]
        messages: List[Dict[Text, Any]] = [
            {"text": message, "quick_replies": []} for message in message_parts
        ]

        # attach all buttons to the last text fragment
        messages[-1]["quick_replies"] = [
            {
                "content_type": "text",
                "title": button["title"],
                "payload": button["payload"],
            }
            for button in buttons
        ]

        for message in messages:
            await self._send_message(recipient_id, message)
            
    async def send_quick_replies(
        self,
        recipient_id: Text,
        text: Text,
        quick_replies: List[Dict[Text, Any]],
        **kwargs: Any,
    ) -> None:
        """Sends quick replies to the output.
        Default implementation will just send as buttons."""

        await self.send_text_with_buttons(recipient_id, text, quick_replies)

    async def send_elements(
        self, recipient_id: Text, elements: Iterable[Dict[Text, Any]], **kwargs: Any
    ) -> None:
        """Sends elements to the output."""

        for element in elements:
            message = {
                "attachment": {
                    "type": "template",
                    "payload": {"template_type": "generic", "elements": element},
                }
            }

            await self._send_message(recipient_id, message)

    async def send_custom_json(
        self, recipient_id: Text, json_message: Dict[Text, Any], **kwargs: Any
    ) -> None:
        """Sends custom json to the output"""

        json_message.setdefault("room", recipient_id)

        await self.sio.emit(self.bot_message_evt, **json_message)

    async def send_attachment(  # type: ignore[override]
        self, recipient_id: Text, attachment: Dict[Text, Any], **kwargs: Any
    ) -> None:
        """Sends an attachment to the user."""
        await self._send_message(recipient_id, {"attachment": attachment})


class IxoInput(InputChannel):
    """An IXO input channel."""

    @classmethod
    def name(cls) -> Text:
        return "ixo"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        credentials = credentials or {}
        return cls(
            credentials.get("user_message_evt", "user_uttered"),
            credentials.get("bot_message_evt", "bot_uttered"),
            credentials.get("namespace"),
            credentials.get("session_persistence", False),
            credentials.get("socketio_path", "/socket.io"),
            credentials.get("jwt_key"),
            credentials.get("jwt_method", "HS256"),
            credentials.get("messages_delay", DEFAULT_DELAY_IN_MESSAGES),
        )

    def __init__(
        self,
        user_message_evt: Text = "user_uttered",
        bot_message_evt: Text = "bot_uttered",
        namespace: Optional[Text] = None,
        session_persistence: bool = False,
        socketio_path: Optional[Text] = "/socket.io",
        jwt_key: Optional[Text] = None,
        jwt_method: Optional[Text] = "HS256",
        messages_delay: int = DEFAULT_DELAY_IN_MESSAGES,
    ):
        """Creates a ``SocketIOInput`` object."""
        self.bot_message_evt = bot_message_evt
        self.session_persistence = session_persistence
        self.user_message_evt = user_message_evt
        self.namespace = namespace
        self.socketio_path = socketio_path
        self.sio: Optional[AsyncServer] = None

        self.jwt_key = jwt_key
        self.jwt_algorithm = jwt_method
        self.messages_delay = messages_delay

    def get_output_channel(self) -> Optional["OutputChannel"]:
        """Creates socket.io output channel object."""
        if self.sio is None:
            rasa.shared.utils.io.raise_warning(
                "SocketIO output channel cannot be recreated. "
                "This is expected behavior when using multiple Sanic "
                "workers or multiple Rasa Open Source instances. "
                "Please use a different channel for external events in these "
                "scenarios."
            )
            return None
        return IxoOutput(self.sio, self.bot_message_evt, self.messages_delay)

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        """Defines a Sanic blueprint."""
        # Workaround so that socketio works with requests from other origins.
        # https://github.com/miguelgrinberg/python-socketio/issues/205#issuecomment-493769183
        sio = AsyncServer(async_mode="sanic", cors_allowed_origins=[])
        socketio_webhook = SocketBlueprint(
            sio, self.socketio_path, "socketio_webhook", __name__
        )

        # make sio object static to use in get_output_channel
        self.sio = sio

        @socketio_webhook.route("/", methods=["GET"])
        async def health(_: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @sio.on("connect", namespace=self.namespace)
        async def connect(sid: Text, environ: Dict, auth: Optional[Dict]) -> bool:
            if self.jwt_key:
                jwt_payload = None
                if auth and auth.get("token"):
                    jwt_payload = rasa.core.channels.channel.decode_bearer_token(
                        auth.get("token"), self.jwt_key, self.jwt_algorithm
                    )

                if jwt_payload:
                    logger.debug(f"User {sid} connected to socketIO endpoint.")
                    return True
                else:
                    return False
            else:
                logger.debug(f"User {sid} connected to socketIO endpoint.")
                return True

        @sio.on("disconnect", namespace=self.namespace)
        async def disconnect(sid: Text) -> None:
            logger.debug(f"User {sid} disconnected from socketIO endpoint.")

        @sio.on("session_request", namespace=self.namespace)
        async def session_request(sid: Text, data: Optional[Dict]) -> None:
            if data is None:
                data = {}
            if "session_id" not in data or data["session_id"] is None:
                data["session_id"] = uuid.uuid4().hex
            if self.session_persistence:
                sio.enter_room(sid, data["session_id"])
            await sio.emit("session_confirm", data["session_id"], room=sid)
            logger.debug(f"User {sid} connected to socketIO endpoint.")

        @sio.on(self.user_message_evt, namespace=self.namespace)
        async def handle_message(sid: Text, data: Dict) -> None:
            output_channel = IxoOutput(sio, self.bot_message_evt, self.messages_delay)

            if self.session_persistence:
                if not data.get("session_id"):
                    rasa.shared.utils.io.raise_warning(
                        "A message without a valid session_id "
                        "was received. This message will be "
                        "ignored. Make sure to set a proper "
                        "session id using the "
                        "`session_request` socketIO event."
                    )
                    return
                sender_id = data["session_id"]
            else:
                sender_id = sid

            message = UserMessage(
                data["message"], output_channel, sender_id, input_channel=self.name()
            )
            await on_new_message(message)

        return socketio_webhook
