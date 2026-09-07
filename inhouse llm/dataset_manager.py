import json
import os
import random
import psycopg2
from psycopg2.extras import DictCursor

class DatasetManagerError(Exception):
    pass

class DatasetManager:
    def __init__(self, data_dir=".", db_connection_string=None):
        self.data_dir = data_dir
        self.train_file = os.path.join(self.data_dir, "clarion_extraction_train.jsonl")
        self.test_file = os.path.join(self.data_dir, "clarion_extraction_test.jsonl")
        self.db_connection_string = db_connection_string

    def build_bootstrap_dataset(self, synthetic_data):
        """
        Step 2: Build the training dataset from the synthetic corpus.
        synthetic_data should be a list of dicts: {"instruction": ..., "input": ..., "output": ...}
        """
        if os.path.exists(self.test_file):
            raise DatasetManagerError(
                "Guardrail 2 Violation: clarion_extraction_test.jsonl already exists. "
                "The test set is frozen at Step 2 and must never be regenerated."
            )

        random.shuffle(synthetic_data)
        split_idx = int(len(synthetic_data) * 0.85)
        train_data = synthetic_data[:split_idx]
        test_data = synthetic_data[split_idx:]

        with open(self.train_file, "w") as f:
            for item in train_data:
                f.write(json.dumps(item) + "\n")

        with open(self.test_file, "w") as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")

        print(f"Bootstrap datasets created. Train: {len(train_data)}, Test: {len(test_data)} (Frozen)")

    def build_recurring_dataset(self):
        """
        Step 7: Recurring pass data preparation.
        Pulls from extraction_correction and blends with original train set.
        """
        if not os.path.exists(self.test_file):
             raise DatasetManagerError("Bootstrap test set not found. Cannot run recurring pass before bootstrap.")
        if not os.path.exists(self.train_file):
             raise DatasetManagerError("Original bootstrap train set not found.")

        # Guardrail 3: Route strictly through extraction_correction table
        corrections = self._fetch_corrections_from_db()
        
        # 1. Reformat corrections to instruction/input/output
        correction_examples = []
        for row in corrections:
            # Assuming row structure maps to the required schema
            # We construct a mock concern text (input) and the corrected JSON (output)
            # In a real scenario, we'd join with the consideration table to get the raw text.
            # For demonstration of the guardrail, we assume the DB provides what we need.
            correction_examples.append({
                "instruction": "Extract structured fields from this RFI concern text.",
                "input": row.get("raw_text", "MOCKED RAW TEXT FOR CORRECTION"), 
                "output": json.dumps({row["field_name"]: row["corrected_value"]})
            })

        # 2. Blend with original synthetic training set
        with open(self.train_file, "r") as f:
            original_train_data = [json.loads(line) for line in f]

        blended_data = original_train_data + correction_examples
        random.shuffle(blended_data)

        recurring_train_file = os.path.join(self.data_dir, "clarion_extraction_train_recurring.jsonl")
        with open(recurring_train_file, "w") as f:
            for item in blended_data:
                f.write(json.dumps(item) + "\n")
        
        print(f"Recurring dataset created with {len(original_train_data)} original and {len(correction_examples)} corrections.")
        return recurring_train_file

    def _fetch_corrections_from_db(self):
        if not self.db_connection_string:
            print("WARNING: No DB connection string provided. Returning mocked corrections to demonstrate Guardrail 3.")
            return [
                 {"field_name": "ctr_article_id", "corrected_value": "Article 42", "raw_text": "Please see Article 42."}
            ]
        
        try:
            # Guardrail 3: Strict query against Section 14.1 schema
            conn = psycopg2.connect(self.db_connection_string)
            cursor = conn.cursor(cursor_factory=DictCursor)
            
            query = """
                SELECT 
                    ec.id,
                    ec.consideration_id,
                    ec.field_name,
                    ec.original_value,
                    ec.corrected_value,
                    c.raw_text -- Assuming a join to get the input text
                FROM extraction_correction ec
                JOIN consideration c ON ec.consideration_id = c.consideration_id;
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return rows
        except Exception as e:
            raise DatasetManagerError(f"Failed to fetch from extraction_correction: {e}")
