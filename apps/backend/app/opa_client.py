import json
import subprocess
import os
import logging

logger = logging.getLogger(__name__)

OPA_BINARY = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../opa"))

def evaluate_policy(policy_file: str, query: str, input_data: dict) -> list:
    """Evaluates input data against a Rego policy file using the local OPA binary."""
    policy_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "policies", policy_file))
    
    if not os.path.exists(OPA_BINARY):
        logger.warning(f"OPA binary not found at {OPA_BINARY}. Returning empty violation list (Mock Mode).")
        return []
        
    try:
        input_json = json.dumps(input_data)
        
        result = subprocess.run(
            [OPA_BINARY, "eval", "-d", policy_path, "-I", "-f", "json", query],
            input=input_json.encode('utf-8'),
            capture_output=True,
            check=True
        )
        
        output = json.loads(result.stdout)
        
        if not output.get("result"):
            return []
            
        violations = []
        for r in output["result"]:
            for v in r.get("expressions", []):
                val = v.get("value", [])
                if isinstance(val, list):
                    violations.extend(val)
                elif isinstance(val, dict):
                     # Sometime OPA returns objects directly
                     pass
        return violations
        
    except subprocess.CalledProcessError as e:
        logger.error(f"OPA Evaluation Error: {e.stderr.decode()}")
        return [{"rule": "OPA-ERROR", "message": "Failed to evaluate policy due to internal error."}]
    except Exception as e:
        logger.error(f"Unexpected OPA error: {str(e)}")
        return [{"rule": "OPA-ERROR", "message": str(e)}]

def check_compliance(rfis: list, considerations: list) -> list:
    """Checks RFI-SLA-001, RFI-SLA-002, FIELDS-001."""
    input_data = {
        "rfis": rfis,
        "considerations": considerations
    }
    return evaluate_policy("clarion_compliance.rego", "data.clarion.compliance.violation", input_data)

def check_governance(request: dict, rfis: list, responses: list) -> list:
    """Checks GATE-001, ACCESS-001."""
    input_data = {
        "request": request,
        "rfis": rfis,
        "responses": responses
    }
    return evaluate_policy("clarion_governance.rego", "data.clarion.governance.deny", input_data)
