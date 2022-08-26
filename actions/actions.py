"""Custom Actions for IXO Assistant"""
# pylint: disable=unused-argument,invalid-name

from typing import Any, Text, Dict, List
import requests

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet

import logging
import json

logger = logging.getLogger(__name__)

ACCEPTABLE_DENOM_VALUES = ["uixo", "atom", "xusd", "regen", "bct", "usdc"]
ACCEPTABLE_AGENT_ROLES = ["SA", "IA", "EA", "none"]

logger.info("Loading actions...")


class ActionMsgSendFormSubmit(Action):
    """Action to be executed at the end of msgSend Form """

    def name(self) -> Text:
        return "action_msgSend_form_submit"

    async def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        logger.info("Running action_msgSend_form_submit...")
        
        transactionType = tracker.get_slot("transactionType")
        
        # Check if the transactionType is faucet
        if transactionType == "faucet":
            logger.info("Transaction type is faucet")
            
            dispatcher.utter_message(response="utter_initiate_faucet")
            # Get the denom slot
            denom = tracker.get_slot("denom")
            # Get the address slot
            # fromAddress = tracker.get_slot("fromAddress")
            toAddress = tracker.get_slot("toAddress")
            # amount = tracker.get_slot("amount")
            # Send await the faucet request
            url = "https://testnet-faucet.ixo.earth/credit"
            
            
            payload = json.dumps({
                "denom": f"{denom}",
                "address": f"{toAddress}"
            })
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            logger.info(f"Sending request to {url} with payload {payload}")
            
            try:
                response = requests.request("POST", url, headers=headers, data=payload)

                logger.info(f"Response from faucet: {response.text}, {response.status_code}, {response}")
                if response.status_code == 200:
                    dispatcher.utter_message(response="utter_faucet_success")
                else:
                    dispatcher.utter_message(text="Response from Faucet: " + response.text)
            except Exception as e:
                logger.error(f"Error sending faucet request: {e}")
                dispatcher.utter_message(text=f"We are unable to serve your request at this time due to {e}")
        else:
            dispatcher.utter_message(response="utter_affirm_transaction")

        return [
            SlotSet('amount',None),
            SlotSet('denom',None),
            SlotSet('toAddress',None),
            SlotSet('memo',None)
            ]


class ActionAgentApplicationFormSubmit(Action):
    """Action to be executed at the end of agentApplication Form """

    def name(self) -> Text:
        return "action_agentApplication_form_submit"

    async def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(response="utter_affirm_agent_application")

        return [
            SlotSet('agentName',None),
            SlotSet('agentRole',None),
            SlotSet('email',None),
            SlotSet('phoneNumber',None),
            SlotSet('longAnswer', None)
            ]

class ValidateMsgSendForm(FormValidationAction):
    """This class validates the msgSend Form Input Fields"""

    def name(self) -> Text:
        return "validate_msgSend_form"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        
        transactionType = tracker.get_slot("transactionType")
        
        logger.info(f"transactionType: {transactionType}")
        
        required_slots = domain_slots.copy()
        
        logger.info("Total Slots: {}".format(required_slots))
        
        if transactionType == "faucet":
            required_slots.remove("amount")
            required_slots.remove("memo")
        else:
            required_slots = ["amount", "denom", "toAddress", "memo"]
        logger.info(f"New Slots for {transactionType}: {required_slots}")
        return required_slots

    def validate_amount(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate amount value."""

        logger.info(f"slot_value: {slot_value}")
        
        if str(slot_value).isdigit():
            dispatcher.utter_message(response="utter_valid_amount")
            return {"amount": slot_value}

        dispatcher.utter_message(response="utter_invalid_amount")
        return {"amount": None}

    def validate_denom(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate denom values. It will take selected values only."""

        logger.info(f"slot_value: {slot_value}")
        
        if slot_value.lower() in ACCEPTABLE_DENOM_VALUES:
            dispatcher.utter_message(response="utter_valid_denom")
            return {"denom": slot_value.lower()}

        dispatcher.utter_message(response="utter_invalid_denom")
        return {"denom": None}

    def validate_toAddress(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate toAddress by checking against cosmos network."""

        logger.info(f"slot_value: {slot_value}")
        
        domain_chain = "testnet"
        endpoint = "cosmos/auth/v1beta1/accounts"
        chain_url = f"https://{domain_chain}.ixo.world/{endpoint}/{slot_value}"

        with requests.session() as sess:
            response = sess.get(chain_url)

            if response.ok:

                result = response.json()

                if "account" in result.keys():
                    dispatcher.utter_message(response="utter_valid_toAddress")
                    return {"toAddress": slot_value}

        dispatcher.utter_message(response="utter_invalid_toAddress")
        return {"toAddress": None}

    def validate_memo(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate memo value."""

        logger.info(f"slot_value: {slot_value}")
        
        dispatcher.utter_message(response="utter_valid_memo")
        return {"memo": slot_value}


class ValidateAgentApplicationForm(FormValidationAction):
    """This class validates the fields against the agentApplication Form"""

    def name(self) -> Text:
        return "validate_agentApplication_form"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:

        return [
            "agentName",
            "agentRole",
            "email",
            "phoneNumber",
            "longAnswer"
        ]

    def validate_agentName(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate agentName value."""
        
        logger.info(f"slot_value: {slot_value}")
        
        if slot_value:
            dispatcher.utter_message(response="utter_valid_agentName")
            return {"agentName": slot_value}

        dispatcher.utter_message(response="utter_invalid_agentName")
        return {"agentName": None}

    def validate_agentRole(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate agentRole value."""
        
        logger.info(f"slot_value: {slot_value}")

        if slot_value in ACCEPTABLE_AGENT_ROLES:
            dispatcher.utter_message(response="utter_valid_agentRole")
            return {"agentRole": slot_value}

        dispatcher.utter_message(response="utter_invalid_agentRole")
        return {"agentRole": None}

    def validate_email(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate email value."""

        logger.info(f"slot_value: {slot_value}")
        
        if slot_value:
            dispatcher.utter_message(response="utter_valid_email")
            return {"email": slot_value}

        dispatcher.utter_message(response="utter_invalid_email")
        return {"email": None}

    def validate_phoneNumber(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate phoneNumber value."""

        logger.info(f"slot_value: {slot_value}")
        
        if slot_value:
            dispatcher.utter_message(response="utter_valid_phoneNumber")
            return {"phoneNumber": slot_value}

        dispatcher.utter_message(response="utter_invalid_phoneNumber")
        return {"phoneNumber": None}

    def validate_longAnswer(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate longAnswer value."""
        
        logger.info(f"slot_value: {slot_value}")

        if slot_value:
            dispatcher.utter_message(response="utter_valid_longAnswer")
            return {"longAnswer": slot_value}

        dispatcher.utter_message(response="utter_invalid_longAnswer")
        return {"longAnswer": None}
    
    