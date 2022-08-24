# ixo Rasa Assistant

## Introduction

The assistant helps users to interact with the ixo platform. It is a simple chatbot that can be work contexually with the ixo platform. It also helps in resolving issues that can arise during the interaction with the platform.

The assistant can be connected to ixo platform through socket.io communication. There is a dedicated channel created specifically to interact with ixo platform. In case of multiple message events from the bot, the channel is used to send the message to the platform by introducing a customizable delay.

## Connecting to the platform

Open the credentials.yml file and fill in the credentials as below:
    
```yaml
addons.channels.ixo.IxoInput:
    user_message_evt: user_uttered
    bot_message_evt: bot_uttered
    session_persistence: true
    messages_delay: 2 # in seconds
```

Here user_message_evt and bot_message_evt are the event names that are used to send the messages to the platform. session_persistence is used to maintain the session between the messages. messages_delay is the delay in seconds between the messages.

The socket.io server is started by running the following command:

```bash
rasa run -m models --endpoints endpoints.yml --credentials credentials.yml
```

And socket.io path is available at **https://{SERVER_IP}:5005/socket.io/**.

