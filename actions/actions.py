"""Custom Actions for IXO Assistant"""
# pylint: disable=unused-argument,invalid-name

from typing import Any, Text, Dict, List
import requests

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet

ACCEPTABLE_DENOM_VALUES = ["IXO", "atom", "xusd", "regen", "bct", "SDC"]


class ActionMsgSendFormSubmit(Action):
    """Action to be executed at the end of msgSend Form """

    def name(self) -> Text:
        return "action_msgSend_form_submit"

    async def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(response="utter_affirm_transaction")

        return [
            SlotSet('amount',None),
            SlotSet('denom',None),
            SlotSet('toAddress',None),
            SlotSet('memo',None)
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

        return [
            "amount",
            "denom",
            "toAddress",
            "memo"
        ]

    def validate_amount(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate amount value."""

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

        dispatcher.utter_message(response="utter_valid_memo")
        return {"memo": slot_value}
