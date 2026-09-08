import json
import random
from pathlib import Path

# Common patterns for EU CTR Validation RFIs
RFI_SCENARIOS = [
    {
        "category": "Missing Signature",
        "msc": "Germany",
        "indication": "Type 2 Diabetes",
        "concerns": [
            "The investigator CV provided for Dr. Schmidt is missing a dated signature.",
            "Please provide a signed version of the Principal Investigator CV for the site in Berlin."
        ],
        "responses": [
            "A signed and dated version of the Principal Investigator CV for Dr. Schmidt has been uploaded to the CTIS portal. Please find the updated document attached.",
            "We acknowledge the missing signature. The updated CV for the Principal Investigator, properly signed and dated, is now provided in the response package."
        ]
    },
    {
        "category": "Translation Discrepancy",
        "msc": "Spain",
        "indication": "Oncology - Solid Tumors",
        "concerns": [
            "There is a discrepancy in the Spanish translation of the Informed Consent Form (ICF) section 4.2 regarding the compensation scheme.",
            "The translated Patient Information Sheet does not align with the master English version on page 3."
        ],
        "responses": [
            "The Spanish translation of the Informed Consent Form has been corrected to accurately reflect the English master version. The updated document (v2.0) has been uploaded.",
            "Thank you for highlighting this discrepancy. The Patient Information Sheet has been revised by our certified translation provider to align perfectly with the English master text."
        ]
    },
    {
        "category": "Missing Part II Document",
        "msc": "France",
        "indication": "Cardiovascular Disease",
        "concerns": [
            "The site suitability form for site 004 in Paris was not included in the initial Part II submission.",
            "Please provide the proof of insurance cover for the clinical trial site located in Lyon."
        ],
        "responses": [
            "The site suitability form for site 004 has been completed and is now included in the updated Part II dossier submission.",
            "The proof of insurance cover for the Lyon site has been obtained and uploaded to the CTIS portal under the Part II documents section."
        ]
    },
    {
        "category": "Protocol formatting",
        "msc": "Italy",
        "indication": "Rheumatoid Arthritis",
        "concerns": [
            "The clinical trial protocol lacks page numbers and a table of contents, which are required for validation.",
            "Please ensure that the protocol document includes a version number and date on every page."
        ],
        "responses": [
            "The clinical trial protocol has been updated to include page numbers and a comprehensive table of contents. Please refer to version 1.1.",
            "We have updated the protocol document format. Version number and date are now clearly visible in the footer of every page."
        ]
    }
]

SYSTEM_PROMPT = "You are an expert regulatory affairs AI. Draft a professional response for the following EU CTR Validation RFI consideration."

def generate_dataset(num_records=100, output_file="apps/backend/dataset/synthetic_rfis.jsonl"):
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    records = []
    
    for _ in range(num_records):
        scenario = random.choice(RFI_SCENARIOS)
        concern = random.choice(scenario["concerns"])
        response = random.choice(scenario["responses"])
        
        # Construct the user prompt
        user_prompt = (
            f"Context: EU CTR Validation RFI\n"
            f"MSC: {scenario['msc']}\n"
            f"Indication: {scenario['indication']}\n"
            f"Concern: {concern}"
        )
        
        # ChatML format (supported by Unsloth/Qwen)
        record = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": response}
            ]
        }
        records.append(record)
        
    with open(output_path, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r) + '\n')
            
    print(f"Successfully generated {num_records} synthetic RFI records at {output_path.absolute()}")

if __name__ == "__main__":
    generate_dataset()
