import base64
import logging
import pickle
from collections import OrderedDict
from pathlib import Path
from typing import Any, List

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import LiteralScalarString

yaml = YAML()
from airtable import Airtable

file_data = open("at.pickle", "rb").read()
file_data = base64.b64decode(file_data)
airtable = pickle.loads(file_data)

def add_training_examples_to_yaml(
    yaml_path: Path, intent: str, training_examples: List[str]
) -> None:
    """Add training examples to the YAML file."""
    
    # check if the file exists else create it
    
    category_name = "faq"
    
    if yaml_path.exists():
        with open(yaml_path, "r") as f:
            data = yaml.load(f)
    else:
        data = CommentedMap()
        data['version'] = '3.1'
        data["nlu"] = CommentedSeq([])
    
    
    nlu = data.get('nlu')
    for i, entry in enumerate(nlu):
        if entry.get('intent') == f"{category_name}/{intent}":
            
            data['nlu'][i]['examples'] = LiteralScalarString(
                "\n".join([f"- {example}" for example in training_examples])
            )
            break
        
    else:
        obj = OrderedDict()
        obj['intent'] = f"{category_name}/{intent}"
        obj['examples'] = LiteralScalarString(
            "\n".join([f"- {example}" for example in training_examples])
            )
        data['nlu'].append(CommentedMap(obj))
    
    # write the file
    with open(yaml_path, "w") as f:
        yaml.dump(data, f)

def sync_airtable_to_yaml():
    
    intent = "Buy"
    records = airtable.iterate(
        "FAQ-Responses",
        # filter_by_formula=f"AND({{intent}}='{intent}')",
        fields=[
            "Intent", "Response", "Long Answer", "Knowledge Resource Link", "Link Title", "Training Examples", "Approved"
            ],
        view="Grid view",
        )

    for record in records:
        
        intent = record['fields']["Intent"]
        training_examples = record["fields"].get("Training Examples", "")
        if training_examples:
            training_examples = training_examples.split("\n")
            training_examples = [example.strip() for example in training_examples]
            training_examples = list(set(training_examples))
            training_examples = list(filter(None, training_examples))
            
            here = Path(__file__).parent.resolve()
            YAML_PATH = here / "data" / "faq.yml"
            
            add_training_examples_to_yaml(YAML_PATH, intent, training_examples)

sync_airtable_to_yaml()
