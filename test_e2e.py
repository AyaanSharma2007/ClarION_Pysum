import httpx
import sys

BASE_URL = "http://localhost:8000"

def run_tests():
    print("Running End-to-End Tests for Clarion...")
    
    with httpx.Client(base_url=BASE_URL) as client:
        # 1. Check Health
        r = client.get("/api/health")
        assert r.status_code == 200, f"Health check failed: {r.text}"
        print("✓ Health Check Passed")
        
        # 2. Intake an RFI (Layer 1)
        intake_payload = {
            "rfi_id": "TEST-RFI-001",
            "msc": {"country": "Germany"},
            "indication": {"name": "Type 2 Diabetes"},
            "due_date": "2026-10-01",
            "response_date": "2026-09-15",
            "submit_date": "2026-09-01",
            "considerations": [
                {
                    "number": 1,
                    "ctr_article": {"name": "Article 6"},
                    "response": {"text": "Provided the data."}
                }
            ]
        }
        r = client.post("/api/rfi/intake", json=intake_payload)
        print(f"Intake Response: {r.status_code}")
        if r.status_code == 200:
            print("✓ Intake Successful")
        else:
            print(f"✗ Intake Failed: {r.text}")
        
        # 3. Create RFI directly (Layer 2)
        rfi_payload = {
            "rfi_type": "validation",
            "msc_id": "Germany",
            "indication_id": "T2D",
            "owner_team": "EU-Hub-Regulatory"
        }
        r = client.post("/rfi", json=rfi_payload)
        print(f"Create RFI Response: {r.status_code}")
        
        if r.status_code == 200:
            rfi_id = r.json()["rfi_id"]
            print(f"✓ Created RFI: {rfi_id}")
            
            # Add Consideration
            cons_payload = {
                "concern_text": "Need more safety data",
                "ctr_article_id": "art-12"
            }
            r = client.post(f"/rfi/{rfi_id}/considerations", json=cons_payload)
            print(f"Add Consideration Response: {r.status_code}")
            
            if r.status_code == 200:
                cons_id = r.json()["consideration_id"]
                print(f"✓ Added Consideration: {cons_id}")
                
                # Add Draft Response
                resp_payload = {"response_text": "Here is the safety data."}
                r = client.post(f"/considerations/{cons_id}/responses", json=resp_payload)
                print(f"Add Response Response: {r.status_code}")
                
                if r.status_code == 200:
                    resp_id = r.json()["response_id"]
                    print(f"✓ Added Draft Response: {resp_id}")
                    
                    # Approve Response (Layer 6 Governance)
                    approve_payload = {"approved_by": "John Doe", "notes": "Looks good"}
                    r = client.post(f"/considerations/{cons_id}/responses/{resp_id}/approve", json=approve_payload)
                    print(f"Approve Response Response: {r.status_code}")
                    if r.status_code == 200:
                        print("✓ Approval Successful")
                    else:
                        print(f"✗ Approval Failed: {r.text}")
                else:
                    print(f"✗ Add Response Failed: {r.text}")
            else:
                print(f"✗ Add Consideration Failed: {r.text}")
                cons_id = None
        else:
            print(f"✗ Create RFI Failed: {r.text}")
        
        # 4. Intelligence Search (Layer 3)
        r = client.get("/search/hybrid?query=adverse+events")
        print(f"Hybrid Search Response: {r.status_code}")
        if r.status_code == 200:
            print("✓ Hybrid Search Successful")
            
        # 5. Risk Predictor (Layer 4)
        risk_payload = {
            "trial_phase": 3,
            "therapeutic_area_oncology": False,
            "therapeutic_area_rare_disease": False,
            "product_class_biologic": True,
            "product_class_atmp": False,
            "has_section_b_protocol": True,
            "has_statistics_section": True,
            "has_impd_quality": False,
            "has_safety_pv_plan": True,
            "has_informed_consent": True,
            "num_mscs": 5,
            "prior_rfi_count": 0
        }
        r = client.post("/api/risk/predict", json=risk_payload)
        print(f"Risk Prediction Response: {r.status_code}")
        if r.status_code == 200:
            print("✓ Risk Prediction Successful")
        else:
            print(f"✗ Risk Prediction Failed: {r.text}")

if __name__ == "__main__":
    run_tests()
