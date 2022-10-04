"""Custom Actions for IXO Assistant"""
# pylint: disable=unused-argument,invalid-name

import base64
from datetime import datetime
import json
import logging
import os
import pickle
import re
from typing import Any, Dict, List, Text

import requests
from airtable import Airtable
from dotenv import load_dotenv
from rasa_sdk import Action, Tracker
from rasa_sdk.events import ActiveLoop, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from recognizers_number import recognize_number
from recognizers_number_with_unit import recognize_currency
from recognizers_text import Culture

logger = logging.getLogger(__name__)

ACCEPTABLE_DENOM = {
    'ixo': "uixo",
    "uixo": "uixo",
    "atom": "atom",
    "xusd": "xusd",
    "regen": "regen",
    "bct": "bct",
    "usdc": "usdc",
    "sdc": "usdc",
    "IXO": "uixo",
    "ATOM": "atom",
    "REGEN": "regen",
    "BCT": "bct",
    "USDC": "usdc",
    "SDC": "usdc",
    "XUSD": "xusd",
}

ACCEPTABLE_AGENT = {
    "sa": "SA",
    "ia": "IA",
    "ea": "EA",
    "SA": "SA",
    "EA": "EA",
    "IA": "IA",
    "none": "none",
    "implementer": "SA",
    "investor": "IA",
    "evaluator": "EA",
    "None": "none",
}

DEFAULT_CHAIN = "testnet"

ACCEPTABLE_DENOM_VALUES = ACCEPTABLE_DENOM.values()
ACCEPTABLE_AGENT_ROLES = ACCEPTABLE_AGENT.values()

load_dotenv()

file_data = open("actions/at.pickle", "rb").read()
file_data = base64.b64decode(file_data)
at = pickle.loads(file_data)

logger.info("Loading actions...")

def extract_amount(text: Text) -> float:
    """Extracts a number from a string"""
    results = recognize_number(text, Culture.English)
    for result in results:
        return float(result.resolution["value"])
    else:
        return None

class ActionFaq(Action):
    
    def name(self) -> Text:
        return "action_faq"
    
    def run(self, dispatcher, tracker, domain):
        
        response_selector = tracker.latest_message.get("response_selector", {}).get("default", {}).get("response", {}).get("intent_response_key","/")
        category, intent = response_selector.split("/")
        
        if category and intent:

            records = at.iterate(
                "faq-response",
                filter_by_formula=f'Intent="{intent}"',
                fields=[
                    "Intent", "Response", "Long Answer", "Knowledge Resource Link", "Link Title"
                    ],
                view="Grid view",
            )
            
            if records:
                for record in records:
                    fields = record["fields"]
                    dispatcher.utter_message(text=fields["Response"])
                    
                    return [
                        SlotSet("retrievalAnswer", fields["Response"]),
                        SlotSet("retrievalLongAnswer", fields.get("Long Answer")),
                        SlotSet("retrievalKnowledgeResourceLink", fields.get("Knowledge Resource Link")),
                        SlotSet("retrievalLinkTitle", fields.get("Link Title")),
                        SlotSet("retrievalIntent", response_selector)
                    ]
                    
                    break

        return []
    
class ActionFaqFollowup(Action):
    
    def name(self) -> Text:
        return "action_faq_followup"
    
    def run(self, dispatcher, tracker, domain):
        
        long_answer = tracker.get_slot("retrievalLongAnswer")
        knowledge_resource_link = tracker.get_slot("retrievalKnowledgeResourceLink")
        knowledge_resource_link_title = tracker.get_slot("retrievalLinkTitle")
        flag = False
        
        if long_answer:
            flag = True
            dispatcher.utter_message(text=long_answer)
        if knowledge_resource_link:
            flag = True
            if knowledge_resource_link_title:
                dispatcher.utter_message(text=f"Visit here [{knowledge_resource_link_title}]({knowledge_resource_link}) for more information.")    
            else:
                dispatcher.utter_message(text=f"Visit this url for more information: {knowledge_resource_link}")    
        
        if not flag:
            dispatcher.utter_message(text="Sorry, I don't have any more information on that.")

        return []

class ActionGreetWallet(Action):
    """Returns a greeting to the user"""

    def name(self) -> Text:
        return "action_greet_wallet"

    def run(self, dispatcher, tracker, domain):
        
        if tracker.active_loop_name:
            dispatcher.utter_message(response="utter_form_interrupted")
        
        dispatcher.utter_message(response="utter_greet_wallet")
        
        return [ActiveLoop(None)]

class ActionMsgSendFormGlobalSlot(Action):
    """Action to set global slot for the form"""

    def name(self) -> Text:
        return "action_msgSend_form_global_slot"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        """Set global slot for the form"""
        
        # Get dayTime like morning, afternoon, evening from current time at GMT+2
        
        now = datetime.now()
        
        if now.hour < 12:
            dayTime = "morning"
        elif now.hour < 17:
            dayTime = "afternoon"
        else:
            dayTime = "evening"
        
        logger.info("Setting global slot for the form")
        
        slots_mapper = {
            "denom": {
                "from_entity": ["denom"],
                # Generate Regex pattern from ACCEPTABLE_DENOM keys
                "regex": f"({'|'.join(ACCEPTABLE_DENOM.keys())})",
            },
            "amount": {
                # "from_entity": ["amount-of-money", "amount", "number"],
                "custom": extract_amount,
            },
            "toAddress": {
                "from_entity": ["toAddress"],
                "regex": r"(ixo|cosmos1)[A-Za-z0-9]{39,41}",
                "from_text": True,
            },
            "memo": {
                "from_entity": ["memo"],
                "from_text": True,
            }
        }
        
        new_slots = {}
        new_slots["daytime"] = dayTime
        
        if tracker.active_loop_name == "msgSend_form":
            
            latest_message = tracker.latest_message
            text = latest_message.get("text")
            entities = latest_message.get("entities")
            
            # Filter the entities that are overlapping with start and end index of the text
            
            
            # Find relevant entities and map them to slots
            for slot_name, slot_mappings in slots_mapper.items():
                logger.info("Slot name: %s", slot_name)
                slot_value = None
                for entity in entities:
                    if entity["entity"] in slot_mappings["from_entity"]:
                        slot_value = entity["value"]
                        break
                if not slot_value and slot_mappings.get("custom"):
                    slot_value = slot_mappings["custom"](text)
                if not slot_value and slot_mappings.get("in_list"):
                    for acceptable_value in slot_mappings["in_list"]:
                        if acceptable_value in text:
                            slot_value = acceptable_value
                            break
                if not slot_value and slot_mappings.get("regex"):
                    defined_regex = slot_mappings["regex"]
                    pattern = re.compile(fr'\b{defined_regex}\b')
                    # pattern = repr('\b' + slot_mappings["regex"]+ '\b')
                    logger.info("Regex: %s", pattern)
                    match = re.search(pattern, text)
                    logger.info("Match: %s", match)
                    if match:
                        slot_value = match.group()
                        logger.info("Slot value: %s", slot_value)
                if not slot_value and slot_mappings.get("from_text"):
                    if tracker.get_slot("requested_slot") == slot_name:
                        slot_value = text
                if slot_value:
                    
                    new_slots[slot_name] = slot_value
                    logger.info(f"Setting {slot_name} to {slot_value}")
            
        logger.info(f"New slots: {new_slots}")
        return [
            SlotSet(name, value)
            for name, value in new_slots.items()
        ]


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
            
            denom = tracker.get_slot("denom")
            toAddress = tracker.get_slot("toAddress")
            
            domain_chain = tracker.get_slot("chain")
            if domain_chain is None:
                domain_chain = "testnet"
                
            url = f"https://{domain_chain}-faucet.ixo.earth/credit"
            
            
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
        
        if transactionType == "faucet":
            required_slots.remove("amount")
            required_slots.remove("memo")
        else:
            required_slots = ["amount", "denom", "toAddress", "memo"]
        return required_slots

    def validate_amount(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate amount value."""

        logger.info(f"Validating Amount slot_value: {slot_value}")
        
        if isinstance(slot_value, (int, float)):
            dispatcher.utter_message(response="utter_valid_amount")
            return {"amount": slot_value}
        
        elif str(slot_value).isdigit():
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

        logger.info(f"Validating Denom slot_value: {slot_value}")
        
        if ACCEPTABLE_DENOM.get(slot_value.lower()):
            dispatcher.utter_message(response="utter_valid_denom")
            return {"denom": ACCEPTABLE_DENOM.get(slot_value.lower())}

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

        logger.info(f"Validating ToAddress slot_value: {slot_value}")
        
        domain_chain = tracker.get_slot("chain")
        if domain_chain is None:
            domain_chain = DEFAULT_CHAIN
            
        endpoint = "cosmos/auth/v1beta1/accounts"
        chain_url = f"https://{domain_chain}.ixo.earth/rest/{endpoint}/{slot_value}"
        dispatcher.utter_message(response="utter_valid_toAddress")
        return {"toAddress": slot_value}

        try:
            with requests.session() as sess:
                response = sess.get(chain_url)

                if response.ok:

                    result = response.json()

                    if "account" in result.keys():
                        dispatcher.utter_message(response="utter_valid_toAddress")
                        return {"toAddress": slot_value}

            dispatcher.utter_message(response="utter_invalid_toAddress")
            return {"toAddress": None}

        except Exception as e:

            logger.error(f"Error validating toAddress: {e}")
            dispatcher.utter_message(text=f"We are unable to serve your request at this time due to {e} and validation of toAddress is being skipped")
            return {"toAddress": slot_value}

    def validate_memo(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate memo value."""

        logger.info(f"Validating Memo slot_value: {slot_value}")
        
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
        
        logger.info(f"Validating AgentName slot_value: {slot_value}")
        
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
        
        logger.info(f"Validating AgentRole slot_value: {slot_value}")

        if ACCEPTABLE_AGENT.get(slot_value.lower()):
            dispatcher.utter_message(response="utter_valid_agentRole")
            return {"agentRole": ACCEPTABLE_AGENT.get(slot_value.lower())}

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

        logger.info(f"Validating Email slot_value: {slot_value}")
        
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

        logger.info(f"Validating PhoneNumber slot_value: {slot_value}")
        
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
        
        logger.info(f"Validating LongAnswer slot_value: {slot_value}")

        if slot_value:
            dispatcher.utter_message(response="utter_valid_longAnswer")
            return {"longAnswer": slot_value}

        dispatcher.utter_message(response="utter_invalid_longAnswer")
        return {"longAnswer": None}
    

class ActionTransactionResult(Action):
    
    def name(self) -> Text:
        return "action_transactionResult"
    
    def run(self, dispatcher, tracker, domain):
        
        logger.info(f"Running ActionTransactionResult")
        
        transaction_hash = tracker.get_slot("transactionHash")
        
        chain = tracker.get_slot("chain")
        if chain is None:
            chain = DEFAULT_CHAIN
        
        transaction_status = None
        message = None
            
        transaction_result_url = f"https://{chain}.ixo.earth/rest/txs/{transaction_hash}"
        headers = {
            'Content-Type': 'application/json'
        }
        
        response = requests.get(transaction_result_url, headers=headers)
        result = response.json()
        logger.info(f"Transaction Result: {result}")
        if response.ok:

            try:
                message = result['tx']['value']['msg'][0]['value']['data']['status']
                if message == "CREATED":
                    transaction_status = "success"
                else:
                    transaction_status = "failed"
            
            except Exception as e:
                logger.exception(msg=e, exc_info=True)
                message = str(e)
                transaction_status = "failed"
                    
        else:
            message = result['error']
            transaction_status = "failed"     

        dispatcher.utter_message(response="utter_transaction_result", transactionStatus=transaction_status)
        
        if transaction_status == "success":
            dispatcher.utter_message(response="utter_transaction_success", blockExplorerUrl = transaction_result_url)
        else:
            dispatcher.utter_message(response="utter_transaction_failed", errorDescription = message)
            
        return [SlotSet("transactionMsg", message), SlotSet("transactionStatus", transaction_status)]

class ActionClaimReward(Action):
    
    def name(self) -> Text:
        return "action_claimReward"
    
    def run(self, dispatcher, tracker, domain):
        
        reward_entity = next(tracker.get_latest_entity_values("reward"), None)
        denom = next(tracker.get_latest_entity_values("denom"), None)
        
        dispatcher.utter_message(response="utter_claim_reward", reward=reward_entity, denom=denom)
