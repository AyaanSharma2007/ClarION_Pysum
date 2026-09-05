import json
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()

def generate_synthetic_rfis(num_rfis=50):
    msc_countries = ["Germany", "Spain", "France", "Italy", "Denmark", "Sweden"]
    indications = ["Type 2 Diabetes Mellitus", "Obesity", "Hemophilia", "Cardiovascular Risk"]
    ctr_articles = ["Annex I, Section 63", "Annex I, Section 50", "Article 5(1)", "Article 6(1)"]
    teams = ["EU-Hub-Regulatory", "RA-Clinical", "Affiliate-DE"]
    
    rfis = []
    
    for _ in range(num_rfis):
        rfi_id = f"CT-2026-{fake.random_int(100000, 999999)}-12-00"
        created_at = fake.date_time_between(start_date="-1y", end_date="now")
        
        rfi = {
            "rfi_id": rfi_id,
            "rfi_type": random.choice(["validation", "assessment"]),
            "status": random.choice(["received", "awaiting_response", "submitted"]),
            "msc_country": random.choice(msc_countries),
            "indication_name": random.choice(indications),
            "owner_team": random.choice(teams),
            "received_at": created_at.isoformat(),
            "considerations": []
        }
        
        # Inject noisy correlations to make SHAP explanation defensible
        if rfi["msc_country"] == "Germany" and rfi["indication_name"] == "Type 2 Diabetes Mellitus":
            num_considerations = random.randint(2, 4) # Germany asks more questions for T2D
        else:
            num_considerations = random.randint(1, 2)
            
        for i in range(num_considerations):
            cons = {
                "consideration_id": f"{rfi_id}-C{i+1}",
                "concern_text": fake.sentence(nb_words=15),
                "ctr_article_name": random.choice(ctr_articles),
                "status": "ready_for_response",
                "responses": []
            }
            
            # If RFI is submitted, add an approved response
            if rfi["status"] == "submitted":
                cons["responses"].append({
                    "id": str(uuid.uuid4()),
                    "response_text": fake.paragraph(nb_sentences=3),
                    "approved_by": fake.name(),
                    "submitted_at": (created_at + timedelta(days=random.randint(2, 9))).isoformat(),
                    "success_score": round(random.uniform(0.5, 1.0), 2)
                })
            rfi["considerations"].append(cons)
            
        rfis.append(rfi)
        
    return rfis

if __name__ == "__main__":
    print("Generating seeded synthetic data for Demo Mode...")
    data = generate_synthetic_rfis(100)
    with open("seeded_rfis.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Generated 100 RFI records in seeded_rfis.json.")
