import base64
import json
import logging
import os
import pickle
import time
from collections import ChainMap, OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Text

import yaml
from airtable import Airtable
from rasa.shared.constants import (DEFAULT_CONFIG_PATH, DEFAULT_DATA_PATH,
                                   DEFAULT_DOMAIN_PATH, INTENT_MESSAGE_PREFIX)
from rasa.shared.core.events import (ActionExecuted, ActiveLoop, SlotSet,
                                     UserUttered)
from rasa.shared.core.training_data.story_writer.yaml_story_writer import \
    YAMLStoryWriter
from rasa.shared.core.training_data.structures import (STORY_START, Checkpoint,
                                                       RuleStep, StoryGraph,
                                                       StoryStep)
from rasa.shared.importers.rasa import Domain
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import LiteralScalarString


class AirtableConnector:
    
    def __init__(self, config_file: str):
        
        self.config = config_file
        
        file_data = open(config_file, "rb").read()
        file_data = base64.b64decode(file_data)
        
        self.base = pickle.loads(file_data)
        
    def yaml_to_dict(text: str):
        """Check the input text in valid yaml format and convert it to dict."""
        
        if not text:
            return {}
        else:
            yaml_dict = yaml.safe_load(text)
            return yaml_dict
        
    def get_table(self, table_name: str, view: str = "Grid view", fields: List[Text] = [], condition = None ) -> List[Dict]:
        if fields:
            if condition:
                return self.base.iterate(table_name, view=view, fields=fields, formula=condition)
            return self.base.iterate(table_name, view=view, fields=fields)
        return self.base.iterate(table_name, view=view)
    
    def get_record_by_id(self, table_name: str, record_id: str) -> Dict:
        return self.base.get(table_name, record_id)
    
    def write_to_yaml(self, path: Path, data: Dict, is_story=False) -> None:
        """Write data to a YAML file."""
        if is_story:
            YAMLStoryWriter().dump(path, data)

        else:
            with open(path, "wb") as w:
                w.write(data)
                w.flush()

        return
    
    def fetch_domain_intents(self):
        intents = []
        for record in self.get_table("Intents", view="Approved"):
            intents.append(
                {
                    record["fields"]["Name"]: {"use_entities": False}
                }
            )
        return intents
    
    def fetch_domain_entities(self):
        entities = []
        
        for record in self.get_table("Entities", view="Approved"):
            entities.append(record["fields"]["Name"])
            
        return entities
        
    def fetch_domain_actions(self):
        
        actions = []
        
        for record in self.get_table("Actions", view="Approved", fields=["Name", "Type"]):

            if record["fields"]["Type"] == "Custom":
                actions.append(record["fields"]["Name"])
        
        
        for record in connector.get_table("Forms", view="Approved"):
            
            if record['fields'].get('RequireValidation'):
                actions.append(f"validate_{record['fields']['form_name']}")
        
        return actions
    
    def fetch_domain_slots(self):
        slots = {}
        
        
        for record in self.get_table("SlotMappings", view="Approved"):
            
            slot_name = record["fields"]["Slot"]
            
            slot_mapping = {}
            
            slot_mapping["type"] = record["fields"]["MappingType"]
            
            if record["fields"].get("MappingValue"):
                
                if record["fields"]["MappingType"] == "from_entity":
                    slot_mapping["entity"] = record["fields"]["MappingValue"]
                elif record["fields"]["MappingType"] == "custom":
                    slot_mapping['action'] = record["fields"]["MappingValue"]
                elif record["fields"]["MappingType"] == "from_intent":
                    slot_mapping["value"] = record["fields"]["MappingValue"]
                    slot_mapping['intent'] = record["fields"]["IntentName"]
            
            if record["fields"].get("Form"):
                slot_mapping["conditions"] = [{
                    "active_loop": record["fields"]["Form"],
                    "requested_slot": slot_name
                    }]

            if not slots.get(slot_name):
                slots[slot_name] = {}
            
            if not slots[slot_name].get("mappings"):
                slots[slot_name]["mappings"] = []
                
            slots[slot_name]['mappings'].append(slot_mapping)
            
            slots[slot_name]['type'] = 'any'
        
        return slots

    def fetch_domain_responses(self):
        responses = {}
        
        for record in self.get_table("Utterances", view="Approved"):
            print(f">>> {record}")
            response_name = record["fields"]["response"]
            
            if not responses.get(response_name):
                responses[response_name] = []
            
            response_value = {}
            
            if record["fields"].get("Text"):
                response_value['text'] = record["fields"]["Text"]
                
            if record["fields"].get("Buttons"):
                temp = record["fields"]["Buttons"]
                print(f">>> fields Buttons {temp}")
                response_value['buttons'] = yaml.safe_load(record["fields"]["Buttons"])
                print(f">>> after yaml.safe_load")
                
            if record["fields"].get("Custom"):
                response_value['custom'] = yaml.safe_load(record["fields"]["Custom"])
            
            responses[response_name].append(response_value)
            
        return responses
        
    def fetch_domain_forms(self):
        forms = {}
        
        for record in self.get_table("Forms", view="Approved"):
            
            form_name = record["fields"]["form_name"]
            required_slots = record["fields"].get("required_slots")
            ignored_intents = record["fields"].get("ignored_intents")
            
            if required_slots:
                forms[form_name] = {
                    'required_slots': required_slots.split(', ')
                }
                
                if ignored_intents:
                    forms[form_name]['ignored_intents'] = ignored_intents.split(', ')

        return forms
    
    def fetch_domain_session_config(self):
        
        return {}
    
    def create_domain(self):
        
        domain_dict = {
            "intents": self.fetch_domain_intents(),
            "entities": self.fetch_domain_entities(),
            "actions": self.fetch_domain_actions(),
            "slots": self.fetch_domain_slots(),
            "responses": self.fetch_domain_responses(),
            "forms": self.fetch_domain_forms(),
            "session_config": self.fetch_domain_session_config(),
        }
        
        return Domain.from_dict(domain_dict)
    
    def write_domain(self):
        
        domain_data = self.create_domain().as_yaml().encode()
        domain_path = DEFAULT_DOMAIN_PATH
        self.write_to_yaml(domain_path, domain_data)
    
    def fetch_stories(self):
        
        stories = {}
        
        for story_step in self.get_table("Stories", view="Approved"):
            
            story_name = story_step["fields"]["Name"]
            
            if not stories.get(story_name):
                stories[story_name] = []
            
            intent = story_step["fields"]["intent_name"]
            actions = story_step["fields"]["action_name"]
            entities = story_step["fields"].get("entity_name")
            
            if entities:
                story_entities = entities
                story_entities_result = [{entity: f"{entity}_value"} for entity in story_entities]
                stories[story_name].append({'intent': intent, "entities": story_entities_result})
            else:
                stories[story_name].append({'intent': intent})
            for action in actions.split(', '):
                stories[story_name].append({'action': action})
                if action.count('_form'):
                    stories[story_name].append({'active_loop': action})
        
        final_stories = []     
        for story_name, story_steps in stories.items():
            final_stories.append({'story': story_name, 'steps': story_steps})
            
        return final_stories
        
    def create_stories(self):
        
        stories = {}
        stories['version'] = '3.1'
        stories['stories'] = self.fetch_stories()
        
        return stories
    
    def fetch_rules(self):
        
        rules = {}
        
        for rule in self.get_table("Rules", view="Approved"):
            
            rule_name = rule["fields"]["Name"]
            
            if not rules.get(rule_name):
                rules[rule_name] = []
                
            if rule['fields']['Type'] == 'Generic':
                
                intent = rule['fields']['intent_name']
                actions = rule['fields']['action_name']
                
                rules[rule_name].append({'intent': intent})
            
                for action in actions.split(', '):
                    rules[rule_name].append({'action': action})
                    
                rules[rule_name].append(rule['fields']['Type'])
            
            elif rule['fields']['Type'] == 'Activate Form':
                
                intent = rule['fields']['intent_name']
                actions = rule['fields']['action_name']
                
                rules[rule_name].append({'intent': intent})
            
                for action in actions.split(', '):
                    rules[rule_name].append({'action': "action_deactivate_loop"})
                    rules[rule_name].append({'active_loop': None})
                    rules[rule_name].append({'action': action})
                    
                    if action.count('_form'):
                        rules[rule_name].append({'active_loop': action})
                        
                rules[rule_name].append(rule['fields']['Type'])
                    
            elif rule['fields']['Type'] == 'Submit Form':
                
                action = rule['fields']['action_name']
                form_name = action.replace('action_', '').replace('utter_', '').replace('_submit', '')
                
                rules[rule_name].append({'action': form_name})
                rules[rule_name].append({'active_loop': None})
                rules[rule_name].append({'slot_was_set': [{'requested_slot': None}]})
                rules[rule_name].append({'action': action})
                
                rules[rule_name].append((rule['fields']['Type'], form_name))
                
        
        final_rules = []
        
        for rule_name, rule_steps in rules.items():
            
            rule_type = rule_steps.pop()
            
            if isinstance(rule_type, tuple):
                rule_type, form_name = rule_type
            
            if rule_type == 'Submit Form':
                final_rules.append({'rule': rule_name, 'steps': rule_steps, 'condition': [{'active_loop': form_name}]})
            
            else:
                final_rules.append({'rule': rule_name, 'steps': rule_steps})
                
        return final_rules
    
    def create_rules(self):
        
        rules = {}
        rules['version'] = '3.1'
        rules['rules'] = self.fetch_rules()
        
        return rules
    
    def write_stories(self):
        
        stories_data = self.create_stories()
        stories_data = yaml.safe_dump(stories_data, default_flow_style=False).encode()

        current_path = Path(os.getcwd())
        stories_path = current_path / "data" / "stories.yml"
        
        # create stories_path if it doesn't exist
        stories_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.write_to_yaml(stories_path, stories_data)
        
    def write_rules(self):
        
        rules_data = self.create_rules()
        rules_data = yaml.safe_dump(rules_data, default_flow_style=False).encode()

        current_path = Path(os.getcwd())
        rules_path = current_path / "data" / "rules.yml"
        
        # create stories_path if it doesn't exist
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.write_to_yaml(rules_path, rules_data)
        
    def create_nlu(self):
        
        data = {}
        data['version'] = '3.1'
        data['nlu'] = []
        
        for record in self.get_table("Intents", view="Approved"):
            
            intent = record["fields"]["Name"]
            training_examples = record["fields"].get("Training Examples", "")
            
            if training_examples:
                training_examples = training_examples.split("\n")
                training_examples = [example.strip() for example in training_examples]
                training_examples = dict.fromkeys(training_examples).keys()
                training_examples = list(filter(None, training_examples))
                
                obj = OrderedDict()
                obj['intent'] = intent
                obj['examples'] = LiteralScalarString(
                    "\n".join([f"- {example}" for example in training_examples])
                    )
                data['nlu'].append(CommentedMap(obj))
            
        return data
        return nlu_data
    
    def write_nlu(self):
        
        nlu_data = self.create_nlu()
        yaml_path = Path(os.getcwd()) / "data" / "nlu.yml"
        
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        
        yaml_writer = YAML()
        
        with open(yaml_path, "w") as f:
            yaml_writer.dump(nlu_data, f)
        
    def create_faq_training_data(self):
        
        category_name = "faq"
        
        data = CommentedMap()
        data['version'] = '3.1'
        data["nlu"] = CommentedSeq([])
        
        for record in self.get_table("FAQ-Responses", view="Approved"):
            
            intent = record['fields']["Intent"]
            training_examples = record["fields"].get("Training Examples", "")
            if training_examples:
                training_examples = training_examples.split("\n")
                training_examples = [example.strip() for example in training_examples]
                # remove duplicates and maintain order
                training_examples = dict.fromkeys(training_examples).keys()
                training_examples = list(filter(None, training_examples))
                
            obj = OrderedDict()
            obj['intent'] = f"{category_name}/{intent}"
            obj['examples'] = LiteralScalarString(
                "\n".join([f"- {example}" for example in training_examples])
                )
            data['nlu'].append(CommentedMap(obj))
            
        return data
    
    def write_faq_training_data(self):
        
        faq_data = self.create_faq_training_data()
        yaml_path = Path(os.getcwd()) / "data" / "faq.yml"
        
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        
        yaml_writer = YAML()
        
        with open(yaml_path, "w") as f:
            yaml_writer.dump(faq_data, f)
            
    def sync(self):
        
        print(f"Trigger Started")
        tik = time.time()
        
        print(f"Preparing the Domain file....")
        self.write_domain()
        print(f"Domain file created")
        
        # self.write_faq_training_data()
        
        print(f"Preparing the NLU file....")
        self.write_nlu()
        print(f"NLU file created")
        
        print(f"Preparing the Stories file....")
        self.write_rules()
        self.write_stories()
        print(f"Stories file created")
        
        tok = time.time()
        
        print(f"Trigger Completed in {tok-tik} seconds")


connector = AirtableConnector('at.pickle')


if __name__ == "__main__":
    connector.sync()
