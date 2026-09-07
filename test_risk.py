import sys
sys.path.append('.')
import asyncio
from apps.backend.app.api.draft_router import _predict_risk_score

concern = "Please confirm that the changes made in protocol version 5.0 dated 18/06/2024 don't impact the ICF/Part II documentation, or withdraw this application in order to resubmit a Part I & Part II application with the updated Part II documentation for all MSCs."
draft = "blah blah"
score = _predict_risk_score(concern, draft, [])
print("Score:", score)
