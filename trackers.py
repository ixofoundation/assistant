import os
import logging
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Text,
    Union,
    TYPE_CHECKING,
    Generator,
)

from rasa.core.tracker_store import TrackerStore, SerializedTrackerAsText, SerializedTrackerAsDict
from rasa.shared.core.domain import Domain
from rasa.core.brokers.broker import EventBroker
from rasa.shared.core.trackers import (
    ActionExecuted,
    DialogueStateTracker,
    EventVerbosity,
)

from pyairtable import Table
from pyairtable.formulas import match

logger = logging.getLogger(__name__)

class AirtableTracker(TrackerStore, SerializedTrackerAsText):
    
    def __init__(
        self,
        domain: Domain,
        base_id: Text,
        api_key: Text,
        table_name: Text,
        event_broker: Optional[EventBroker] = None,
        **kwargs: Dict[Text, Any],
    ) -> None:
        """Initializes the tracker store."""
        self.store: Dict[Text, Text] = {}
        
        self.table = Table(
            api_key=api_key,
            base_id=base_id,
            table_name=table_name
        )
        
        self.store: Dict[Text, Text] = {}
        
        logger.info(f"Connected to Airtable Table: {table_name}")
        
        super().__init__(domain, event_broker, **kwargs)
        
    def keys(self) -> Iterable[Text]:
        """Returns all keys of the store."""
        return self.store.keys()
    
    def retrieve(self, sender_id: Text) -> Optional[DialogueStateTracker]:
        """Returns tracker matching sender_id."""
        if sender_id in self.store:
            logger.debug(f"Recreating tracker for id '{sender_id}'")
            return self.deserialise_tracker(sender_id, self.store[sender_id])

        logger.debug(f"Could not find tracker for conversation ID '{sender_id}'.")

        return None
    
    def save(self, tracker: DialogueStateTracker) -> None:
        """Updates and saves the current conversation state."""
        self.stream_events(tracker)
        
        state = tracker.current_state(EventVerbosity.ALL)
        
        self.add_to_store(tracker.sender_id, state)
        
        serialised = AirtableTracker.serialise_tracker(tracker)
        self.store[tracker.sender_id] = serialised
    
    def add_to_store(self, sender_id: Text, state: Dict[Text, Any]) -> None:
        """Adds the latest message and metadata to airtable Table"""
        
        latest_message = state.get("latest_message", {})
        events = state.get("events", [])
        
        message = None
        timestamp = None
        intent = None
        entities = {}
        confidence = None
        found = True
        
        logger.info(f"Latest Message: {latest_message}")

        if latest_message:
            
            for event in events[::-1]:
                
                if event['event'] == "user":
                    
                    message = event['text']
                    timestamp = event['timestamp']
                    intent = event['parse_data']['intent']['name']
                    entities = event['parse_data']['entities']
                    confidence = event['parse_data']['intent']['confidence']
                    
                    break
            
            key = f"{sender_id}-{timestamp}"
            found = True
            logger.info(f"Message: {message} Intent: {intent} Key: {key}")
            if message and intent and key:
                
                formula = match({"intent": intent, "message": message, "key": key})
                logger.info(f"Formula: {formula}")
                found = self.table.first(formula=formula)
                bool_found = bool(found)
                logger.info(f"Found: {found}, Bool Found: {bool_found}")
                if not found:
                    self.table.create({"intent": intent, "message": message, "confidence":confidence, "entities":str(entities), "key": key})
                    logger.info(f"Created Message: {message} Intent: {intent} Key: {key}")
