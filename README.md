# ixo Rasa Assistant

## Introduction

The assistant helps users to interact with the ixo platform. It is a simple chatbot that can be work contexually with the ixo platform. It also helps in resolving issues that can arise during the interaction with the platform.

The assistant can be connected to ixo platform through socket.io communication. There is a dedicated channel created specifically to interact with ixo platform. In case of multiple message events from the bot, the channel is used to send the message to the platform by introducing a customizable delay.

## Connecting to the platform

Open the credentials.yml file and fill in the credentials as below:
    
```yaml
channels.IxoInput:
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


## Creating the assistant in Airtable
All training data and stories are available in the data folder. However, the assistant training data and stories were managed by modifying the data in the airtable base. The airtable base is available here:

https://airtable.com/app8EgyXNUmeykw8p/tblheCSnctt4b7qhY/viwNwvM2Y8siu9aKN?blocks=hide

The base contains the following tables:

1. Control Panel: This table contains buttons to execute the actions. The buttons are used to train the assistant.

2. NLU-Inbox: This table contains all the messages that are sent to the assistant. The messages are used to train the assistant. These messages needs to be annotated so as to train the assistant.

3. Intents: This table contains all the available intents in the assistant. These are all the intents that are supported by the assistant. When a new intent is added, it needs to be added to this table. Intents can be added by adding a new row in the table. Also, the entities needs mapped to the intent. The entities are added in the Entities table. For each intent, we need to provide the training phrases. The training phrases are added in the Training Examples fiels. The annotated training phrases are used to train the assistant.

4. Entities: This table contains all the available entities in the assistant. These are all the entities that are supported by the assistant. When a new entity is added, it needs to be added to this table. Also, we need to map these entities to the intents.

5. Slots: Slots are bot's memory. These slots are used to store the information that is collected from the user. These slots are basic data types like text, number, boolean, list, etc. When a new slot is added, it needs to be added to this table. Also, we need to define the mappings for the slots. The mappings are added in the SlotMappings table.

6. SlotMappings: We need to define the mappings for each slot that is defined in Slots table. The mappings are of different types and generally depends on the type of the slot. We also need to give priority to the mappings. The higher the priority, the more important the mapping is. When a new mapping is added, it needs to be added to this table. While adding the mapping, we need to select mainly three things:

    6.1. MappingType: The mapping type can be one of the from_entity, from_text, from_intent and custom. The mapping type defines how the slot is filled. For example, if the mapping type is from_entity, then the slot is filled by extracting the entity from the user message. If the mapping type is from_text, then the slot is filled by extracting the text from the user message. If the mapping type is from_intent, then the slot is filled by the MappingValue specified when the intent in the Intent field matches. If the mapping type is custom, then the slot is filled by custom code. We need to specify the custom action code name in the Mapping value field.

    6.2. MappingValue: Depending upon the value selected in MappingType field, we need to write the value here. 
    If the type is from_entity, we need to write the entity name here.
    If the type is from_intent, we need to write the value that needs to be filled here.
    If the type is custom, we need to write the action code name here.
    Otherwise, we can leave this blank for now.

    6.3. Intent: This field is necessary only when the mapping type is from_intent. We need to select the intent here.

    6.4. FillOnlyInForm: This field is optional and is used to specify whether the slot needs to be filled only when the form is active. If this field is checked, then the slot is filled only when the form is active. Otherwise, the slot is filled even when the form is not active.

7. Actions: Actions are the tasks that the assistant can perform. We need to add all actions that are supported by the assistant along with it's type. Mainly the actions are of three types. They are:

    7.1. Utterance Actions: These actions are the responses that we want the assistant to send to the user. These responses might contain different media like text, image, video, etc. When a new utterance action is added, we need to define the responses for the utterance in Utterances table.

    7.2. Form Actions: These actions are used to collect information from the user.  When a new form action is added, we need to define the slots that are used in the form in Forms table. Also, we need to define the mappings for the slots in SlotMappings table.

    7.3. Custom Actions: These actions are used to perform custom tasks. When a new custom action is added, we need to define the code in the git repository. The code needs to be added in the actions folder.

It is really important to add all the actions, intents, entities, slots, etc. in the respective tables. Otherwise, the assistant will not be able to train properly. While adding the actions, we need to select the action type. Based on the action type, the assistant will be able to train the assistant properly.

8. Utterances: This table contains all the utterances that are used in the assistant. When a new utterance is added in the Actions, we need to add the utterance in this table. Also, we need to define the response type for the utterance. Right now, the utterance supports three types of responses. They are:

    8.1. Text: This is the default response type. We can add the text response in the Text field.

    8.2. Button: This response type is used to send the buttons to the user. We need to add the buttons in the Buttons field. The buttons are added in the format of specified below.
    
    ```
    - payload: SA
      title: Implementer
    - payload: IA
      title: Investor
    ```

    Here title will be displayed in the button and payload will be sent to the assistant when the button is clicked.

    8.3. Custom: This response type is used to send the custom response to the user. We need to add the custom response in the Custom field. The custom response is added in the format of specified below.
    
    ```
    data:
      value:
        - agentRole: '{agentRole}'
        - name: '{agentName}'
        - email: '{email}'
        - phoneNumber: '{phoneNumber}'
        - motivation: '{longAnswer}'
    response:
      did: '{userDid}'
      trigger: proto_msg
      type: project/CreateAgent
    ```

9. Forms: This table contains all the forms that are used in the assistant. When a new form is added in the Actions, we need to add the form in this table. Also, we need to define the slots that are used in the form in this table in RequiredSlots field. The slots need to be selected from the Slots table. Here, the slots are added in the order in which they are asked to the user. When we add slots for Forms, we also need to define an Utterance action for the form. This utterance action is used to ask the user to fill the form. We need to add the utterance action in the Actions table. Also, we need to add the utterance in the Utterances table. The name of the Utterance action has to be in the format utter_ask_{slot_name} where slot_name is the name of the slot that is asked first in the form. For example, if the first slot in the form is agentRole, then the utterance action name should be utter_ask_agentRole.
When we add form, we also need to make sure whether we need any validation of each slot. If we need validation, we need to check the field RequireValidation. The validation logic needs to be written in the custom action server.

10. Stories: The stories define the contexual behaviour of the assistant. When we add stories, we need to add them as step wise. For each step, we need to select the intent and entity combination and action that we wanted. For the action, we can chose custom actions and utterance actions. The name of the story needs to be same for multi steps.

11. Rules: Rules are used to define the behaviour of the assistant when the user message does not match any of the stories. When we add rules, those actions will be taken irrespective of the context of the conversation. These are single step actions. Rules are useful for triggering forms, submitting forms and other actions that are not context dependent. Like stories, we also need to map intent with action. For form submissions, we don't need to select any intent. We can directly select the action. The action name has to be action_{form_name}_submit. For example, if the form name is agentForm, then the action name should be action_agentForm_submit.


## Training the assistant

The assistant can be trained by clicking the Run Script button in Control Panel table. This will trigger the training script workflow defined in the github actions. The github actions will trigger the training script in the assistant server. The training script will train the assistant and update the assistant model in the assistant server. We need to manually set the model active in the assistant server. The assistant server will automatically update the model in the assistant client. The assistant client will automatically update the model in the assistant app.

## Testing the assistant

One can test the assistant by logging in [Rasa X](https://assistant.ixo.earth) website
