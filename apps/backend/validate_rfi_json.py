"""
RFI Nexus — pre-load validator.

Run this BEFORE load_rfi.py on a batch of your teammate's parser output.
It catches two categories of problem cheaply, before they reach Neo4j:

  1. Structural errors — missing required fields, wrong types — using the
     JSON Schema in rfi_extraction_schema.json.
  2. Near-duplicate merge-key values across files — e.g. "Germany" vs "DE"
     vs "germany" — which jsonschema validation alone won't catch, since
     each value is individually valid, just inconsistent across files.

Usage:
    pip install jsonschema
    python validate_rfi_json.py path/to/json_folder/
"""

import os
import sys
import json
from collections import defaultdict
from jsonschema import validate, ValidationError
import pathlib
DEFAULT_SCHEMA = pathlib.Path(__file__).parent.parent.parent / "schemas" / "rfi_extraction_schema.json"

def load_schema(schema_path=DEFAULT_SCHEMA):
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_structure(filepath, schema):
    with open(filepath, "r", encoding="utf-8") as f:
        record = json.load(f)
    try:
        validate(instance=record, schema=schema)
        return record, None
    except ValidationError as e:
        return None, f"{os.path.basename(filepath)}: {e.message} (at {'/'.join(str(p) for p in e.path)})"


def check_naming_consistency(records):
    """Flags merge-key values that look like the same real-world thing
    spelled differently — a cheap heuristic (case + whitespace fold),
    not a substitute for a human skim of the flagged groups."""
    seen = defaultdict(set)
    for r in records:
        seen["msc.country"].add(r["msc"]["country"])
        seen["indication.name"].add(r["indication"]["name"])
        for c in r["considerations"]:
            seen["ctr_article.name"].add(c["ctr_article"]["name"])

    warnings = []
    for field, values in seen.items():
        folded = defaultdict(list)
        for v in values:
            folded[v.strip().lower()].append(v)
        for key, variants in folded.items():
            if len(variants) > 1:
                warnings.append(f"{field}: possible duplicate spellings {variants} — will create separate nodes unless fixed")
    return warnings


def main(json_folder, schema_path=DEFAULT_SCHEMA):
    schema = load_schema(schema_path)
    if os.path.isfile(json_folder):
        files = [json_folder]
    else:
        files = [os.path.join(json_folder, f) for f in os.listdir(json_folder) if f.endswith(".json")]

    valid_records = []
    errors = []
    for filepath in files:
        record, error = validate_structure(filepath, schema)
        if error:
            errors.append(error)
        else:
            valid_records.append(record)

    print(f"Checked {len(files)} files: {len(valid_records)} valid, {len(errors)} failed structural validation.\n")

    if errors:
        print("STRUCTURAL ERRORS (fix these before loading — the file will be skipped otherwise):")
        for e in errors:
            print(f"  - {e}")
        print()

    warnings = check_naming_consistency(valid_records)
    if warnings:
        print("NAMING CONSISTENCY WARNINGS (structurally valid, but check these manually):")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("No naming inconsistencies detected across merge-key fields.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_rfi_json.py <path/to/json_folder>")
        sys.exit(1)
    main(sys.argv[1])