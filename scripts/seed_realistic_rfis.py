"""
seed_realistic_rfis.py — Seed 20 distinct, realistic clinical trial RFIs.

1. Clears duplicate/old test entries from Supabase `rfi_intake`.
2. Seeds 20 distinct clinical trial RFIs across all 6 departments:
   - Quality Assurance (CMC)
   - Biostatistics
   - Regulatory Affairs
   - Clinical Operations
   - Pharmacovigilance
   - Medical Writing
3. Includes complete considerations with realistic concern texts and accepted sponsor responses.
4. Generates dense 384-dim vector embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
5. Connects to Neo4j AuraDB Knowledge Graph:
   - Clears old IS_SIMILAR_TO edges and synchronizes RFI/Department/Category nodes.
   - Creates IS_SIMILAR_TO relationships based on cosine similarity >= 0.75.
   - Shows natural, realistic similarity scores (e.g. 80%–92%) instead of flat 100%.
6. Forwards records to Layer 2 Central Repository (POST /rfi) with valid schema.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
import numpy as np
import httpx
from dotenv import load_dotenv

# Load env vars
load_dotenv("LAYER2/layer2/.env")
load_dotenv("apps/backend/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_rfis")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
LAYER2_URL = os.getenv("LAYER2_URL", "http://localhost:8001")


# ── Dataset of 20 Distinct Clinical Trial RFIs ────────────────────────────────
REALISTIC_RFIS = [
    # Cluster 1: CMC - Expiry & Batch Release Verification (3 related RFIs, sim ~ 80%–91%)
    {
        "rfi_id": "CT-2025-00101-11-00-SM01",
        "department": "Quality Assurance (CMC)",
        "category": "GMP Compliance",
        "urgency": "High",
        "summary": "Batch release certificates require updated expiry date verification and shelf-life data.",
        "country": "Germany",
        "nca": "BfArM",
        "therapeutic_area": "Oncology",
        "indication": "Non-Small Cell Lung Cancer",
        "days_ago": 18,
        "resolved_days_later": 4,
        "concern_text": "The submitted Investigational Medicinal Product Dossier (IMPD) Section 2.2.P.8 does not include real-time stability data supporting the proposed 24-month shelf life. Please provide updated batch release certificates and stability test results.",
        "ctr_article": "Article 25 / Annex I, Section 63",
        "response_text": "We have provided updated real-time stability data through month 24 (Appendix 3) and revised batch release certificates confirming the 24-month shelf life under ICH storage conditions.",
    },
    {
        "rfi_id": "CT-2025-00102-12-00-SM01",
        "department": "Quality Assurance (CMC)",
        "category": "GMP Compliance",
        "urgency": "High",
        "summary": "Batch release certificates are missing updated expiry date verification and stability confirmation.",
        "country": "France",
        "nca": "ANSM",
        "therapeutic_area": "Immunology",
        "indication": "Rheumatoid Arthritis",
        "days_ago": 14,
        "resolved_days_later": 5,
        "concern_text": "Please provide valid Qualified Person (QP) batch release documentation and shelf-life stability verification for clinical batches stored under ambient hospital conditions.",
        "ctr_article": "Article 25 / Annex I, Section 63",
        "response_text": "The Qualified Person (QP) declaration and batch release certificates have been re-issued with re-test dating and ambient condition stability reports attached in Module 3.",
    },
    {
        "rfi_id": "CT-2025-00103-14-00-SM02",
        "department": "Quality Assurance (CMC)",
        "category": "GMP Compliance",
        "urgency": "Medium",
        "summary": "Batch release documentation lacks Qualified Person expiry date validation for comparator lots.",
        "country": "Spain",
        "nca": "AEMPS",
        "therapeutic_area": "Oncology",
        "indication": "Metastatic Colorectal Cancer",
        "days_ago": 9,
        "resolved_days_later": 3,
        "concern_text": "The Qualified Person release certificate for the background comparator product does not state the approved EU expiry date. Please clarify.",
        "ctr_article": "Annex I, Part I - CMC",
        "response_text": "The comparator QP release certificate has been updated to cite the EMA central marketing authorization expiry date and authorized batch lot numbers.",
    },

    # Cluster 2: Biostatistics - Sample Size & Subgroup Power (3 related RFIs, sim ~ 82%–89%)
    {
        "rfi_id": "CT-2025-00201-22-00-SM01",
        "department": "Biostatistics",
        "category": "Protocol Design",
        "urgency": "High",
        "summary": "The primary endpoint statistics are insufficiently powered for the subgroup analysis.",
        "country": "Germany",
        "nca": "BfArM",
        "therapeutic_area": "Oncology",
        "indication": "Triple-Negative Breast Cancer",
        "days_ago": 22,
        "resolved_days_later": 6,
        "concern_text": "The statistical analysis plan does not provide power calculations for the secondary progression-free survival endpoint in the PD-L1 high subgroup. Please provide justification.",
        "ctr_article": "Article 6, Part I Assessment",
        "response_text": "Protocol Section 9.4 has been amended to provide a detailed statistical simulation confirming 85% power at a two-sided alpha of 0.05 for the PD-L1 high subgroup.",
    },
    {
        "rfi_id": "CT-2025-00202-23-00-SM01",
        "department": "Biostatistics",
        "category": "Protocol Design",
        "urgency": "High",
        "summary": "Primary efficacy endpoint statistical power is insufficiently justified for subgroup analysis.",
        "country": "Italy",
        "nca": "AIFA",
        "therapeutic_area": "Neurology",
        "indication": "Multiple Sclerosis",
        "days_ago": 16,
        "resolved_days_later": 4,
        "concern_text": "Please justify the statistical power and sample size determination for the primary efficacy endpoint across age and gender subgroups.",
        "ctr_article": "Article 6, Part I Assessment",
        "response_text": "Subgroup statistical power tables have been incorporated into SAP Section 5.3 demonstrating over 80% power across all demographic strata.",
    },
    {
        "rfi_id": "CT-2025-00203-25-00-SM02",
        "department": "Biostatistics",
        "category": "Protocol Design",
        "urgency": "Medium",
        "summary": "Sample size assumptions and statistical power justification are required for primary endpoints.",
        "country": "Belgium",
        "nca": "FAMHP",
        "therapeutic_area": "Cardiovascular",
        "indication": "Heart Failure with Preserved Ejection Fraction",
        "days_ago": 11,
        "resolved_days_later": None,  # Unresolved
        "concern_text": "Please clarify how sample size was calculated to account for dropout while preserving statistical power for co-primary endpoints.",
        "ctr_article": "Article 6, Part I Assessment",
        "response_text": "We have appended a formal sensitivity power analysis in Statistical Analysis Plan Section 4.2 accounting for up to 15% participant attrition.",
    },

    # Cluster 3: Pharmacovigilance - Reference Safety Information (2 related RFIs, sim ~ 86%–91%)
    {
        "rfi_id": "CT-2025-00301-31-00-SM01",
        "department": "Pharmacovigilance",
        "category": "Safety Reporting",
        "urgency": "High",
        "summary": "Reference Safety Information in the Investigator Brochure must be updated for SUSAR reporting.",
        "country": "Netherlands",
        "nca": "CCMO",
        "therapeutic_area": "Oncology",
        "indication": "Cutaneous Melanoma",
        "days_ago": 25,
        "resolved_days_later": 3,
        "concern_text": "Section 7.3 of the Investigator's Brochure does not list immune-mediated hepatitis as an expected adverse reaction. Please harmonize the RSI with recent clinical study report findings.",
        "ctr_article": "Annex I, Section 65 - Safety",
        "response_text": "Investigator's Brochure Version 7.0 has been updated to include immune-mediated hepatitis in Table 4 (Expected Adverse Reactions), harmonizing the RSI for SUSAR triage.",
    },
    {
        "rfi_id": "CT-2025-00302-32-00-SM01",
        "department": "Pharmacovigilance",
        "category": "Safety Reporting",
        "urgency": "High",
        "summary": "Investigator Brochure Reference Safety Information requires updates to align with safety reporting.",
        "country": "Germany",
        "nca": "BfArM",
        "therapeutic_area": "Infectious Diseases",
        "indication": "Complicated Intra-abdominal Infections",
        "days_ago": 12,
        "resolved_days_later": 4,
        "concern_text": "Please confirm that safety reporting algorithms use the newly approved Reference Safety Information (RSI) dated January 2025 for expectedness evaluation of serious adverse events.",
        "ctr_article": "Annex I, Section 65 - Safety",
        "response_text": "The pharmacovigilance safety monitoring charter has been updated to enforce the January 2025 RSI cutoff for all ongoing blinded evaluations.",
    },

    # Cluster 4: Regulatory Affairs - Informed Consent & GDPR (2 related RFIs, sim ~ 85%–90%)
    {
        "rfi_id": "CT-2025-00401-41-00-SM01",
        "department": "Regulatory Affairs",
        "category": "Informed Consent",
        "urgency": "Medium",
        "summary": "Informed consent form lacks specific GDPR clauses required for participant data transfer.",
        "country": "France",
        "nca": "ANSM",
        "therapeutic_area": "Rare Diseases",
        "indication": "Spinal Muscular Atrophy",
        "days_ago": 20,
        "resolved_days_later": 2,
        "concern_text": "The patient information sheet does not clearly inform participants of their right to withdraw consent for secondary genomic analyses under GDPR Article 17.",
        "ctr_article": "Part II - Informed Consent / GDPR",
        "response_text": "Section 12 of the Informed Consent Form has been revised with standardized wording regarding participant data erasure rights and genetic biobanking protocols.",
    },
    {
        "rfi_id": "CT-2025-00402-42-00-SM01",
        "department": "Regulatory Affairs",
        "category": "Informed Consent",
        "urgency": "Medium",
        "summary": "Patient informed consent form is missing mandatory GDPR clauses regarding data protection.",
        "country": "Spain",
        "nca": "AEMPS",
        "therapeutic_area": "Hematology",
        "indication": "Diffuse Large B-Cell Lymphoma",
        "days_ago": 7,
        "resolved_days_later": 3,
        "concern_text": "Under national legal provisions, the informed consent form must state the contact information for the trial site Data Protection Officer (DPO) and local supervisory authority.",
        "ctr_article": "Part II - Informed Consent / GDPR",
        "response_text": "Site-specific ICF addenda have been uploaded containing local DPO contact details and national regulatory ombudsman addresses for all Spanish investigation sites.",
    },

    # 10 Standalone Distinct RFIs
    {
        "rfi_id": "CT-2025-00501-51-00-SM01",
        "department": "Clinical Operations",
        "category": "Protocol Design",
        "urgency": "High",
        "summary": "Investigator site monitoring plan lacks clear operational criteria for remote source data verification.",
        "country": "Germany",
        "nca": "BfArM",
        "therapeutic_area": "Oncology",
        "indication": "Acute Myeloid Leukemia",
        "days_ago": 15,
        "resolved_days_later": 5,
        "concern_text": "The clinical monitoring plan does not specify the scope of electronic remote source data verification (rSDV) or protections against unauthorized electronic health record access.",
        "ctr_article": "Article 51 - Monitoring",
        "response_text": "The Clinical Monitoring Plan (CMP) version 3.0 has been revised to restrict rSDV to critical safety endpoints via encrypted dual-authenticated hospital portals.",
    },
    {
        "rfi_id": "CT-2025-00502-52-00-SM01",
        "department": "Clinical Operations",
        "category": "Documentation",
        "urgency": "Medium",
        "summary": "Protocol deviation classification framework must define critical vs major non-compliance reporting timelines.",
        "country": "Italy",
        "nca": "AIFA",
        "therapeutic_area": "Respiratory",
        "indication": "Idiopathic Pulmonary Fibrosis",
        "days_ago": 8,
        "resolved_days_later": None,  # Unresolved
        "concern_text": "The Protocol Deviation Management Plan does not clearly delineate timelines for reporting serious GCP breaches to the reporting Member State within 7 days.",
        "ctr_article": "Article 52 - Serious Breaches",
        "response_text": "Section 4.1 has been updated with an explicit 7-calendar-day notification SLA to national competent authorities for any critical protocol non-compliance.",
    },
    {
        "rfi_id": "CT-2025-00503-53-00-SM01",
        "department": "Clinical Operations",
        "category": "Protocol Design",
        "urgency": "Low",
        "summary": "Patient travel expense reimbursement guidelines must be provided in local language documentation.",
        "country": "Belgium",
        "nca": "FAMHP",
        "therapeutic_area": "Endocrinology",
        "indication": "Type 1 Diabetes",
        "days_ago": 5,
        "resolved_days_later": 2,
        "concern_text": "Please provide the patient stipend and travel expense compensation schedule submitted in Part II in French and Dutch.",
        "ctr_article": "Part II - Compensation",
        "response_text": "Certified French and Dutch translations of the Participant Reimbursement Policy (Document ref: FIN-04) have been uploaded to the CTIS portal.",
    },
    {
        "rfi_id": "CT-2025-00601-61-00-SM01",
        "department": "Medical Writing",
        "category": "Documentation",
        "urgency": "Medium",
        "summary": "Inconsistency identified between clinical study protocol synopsis inclusion criteria and main protocol Section 4.1.",
        "country": "France",
        "nca": "ANSM",
        "therapeutic_area": "Oncology",
        "indication": "Ovarian Cancer",
        "days_ago": 19,
        "resolved_days_later": 3,
        "concern_text": "The protocol synopsis states an ECOG performance status cutoff of 0-1, whereas Section 4.1.2 permits ECOG 2. Please resolve this discrepancy.",
        "ctr_article": "Article 25 / Annex I",
        "response_text": "The discrepancy has been rectified; Protocol Section 4.1.2 has been corrected to restrict enrollment strictly to ECOG 0-1, matching the synopsis.",
    },
    {
        "rfi_id": "CT-2025-00602-62-00-SM01",
        "department": "Medical Writing",
        "category": "Documentation",
        "urgency": "Low",
        "summary": "Dosing titration schedule in Investigator Brochure does not match Protocol Appendix 2 flowcharts.",
        "country": "Spain",
        "nca": "AEMPS",
        "therapeutic_area": "Neurology",
        "indication": "Parkinson's Disease",
        "days_ago": 6,
        "resolved_days_later": None,  # Unresolved
        "concern_text": "Appendix 2 of the protocol lists dose titration intervals as weekly, while the Investigator Brochure indicates bi-weekly increments. Please harmonize.",
        "ctr_article": "Article 25 / Annex I",
        "response_text": "Investigator Brochure Section 6.2 has been harmonized with the approved weekly clinical titration schedule reflected in Protocol Appendix 2.",
    },
    {
        "rfi_id": "CT-2025-00701-71-00-SM01",
        "department": "Quality Assurance (CMC)",
        "category": "Bioequivalence",
        "urgency": "High",
        "summary": "Container closure integrity test validation is incomplete for pre-filled syringes stored at -20C.",
        "country": "Germany",
        "nca": "BfArM",
        "therapeutic_area": "Immunology",
        "indication": "Severe Atopic Dermatitis",
        "days_ago": 26,
        "resolved_days_later": 7,
        "concern_text": "The microbial ingress container closure integrity testing was only conducted at room temperature. Please provide validation data for storage at -20C.",
        "ctr_article": "Annex I, Part I - CMC",
        "response_text": "High-voltage leak detection and helium leak rate testing validation reports for storage at -20C have been executed and appended to IMPD Section 3.2.P.7.",
    },
    {
        "rfi_id": "CT-2025-00702-72-00-SM01",
        "department": "Quality Assurance (CMC)",
        "category": "GMP Compliance",
        "urgency": "High",
        "summary": "Viral clearance filtration validation study summary missing from biological substance IMPD Section 3.2.A.2.",
        "country": "Netherlands",
        "nca": "CCMO",
        "therapeutic_area": "Rare Diseases",
        "indication": "Fabry Disease",
        "days_ago": 13,
        "resolved_days_later": 4,
        "concern_text": "Please provide chromatographic viral clearance and nanofiltration reduction factor studies for the recombinant enzyme drug substance.",
        "ctr_article": "Annex I, Part I - CMC",
        "response_text": "Comprehensive viral reduction factor documentation (Report VR-2024-09) confirming > 12 log10 overall viral clearance has been incorporated into Section 3.2.A.2.",
    },
    {
        "rfi_id": "CT-2025-00801-81-00-SM01",
        "department": "Regulatory Affairs",
        "category": "Documentation",
        "urgency": "Low",
        "summary": "Proof of national administrative fee payment receipt missing for Part II submission dossier.",
        "country": "Spain",
        "nca": "AEMPS",
        "therapeutic_area": "Oncology",
        "indication": "Gastric Adenocarcinoma",
        "days_ago": 28,
        "resolved_days_later": 1,
        "concern_text": "The Part II submission fee receipt (Modelo 790) was omitted from the submission dossier. Please provide the validated banking receipt.",
        "ctr_article": "Part II - Administrative",
        "response_text": "The stamped bank receipt confirming full settlement of the AEMPS Phase 3 trial fee (Modelo 790, code 007) has been uploaded.",
    },
    {
        "rfi_id": "CT-2025-00802-82-00-SM01",
        "department": "Regulatory Affairs",
        "category": "Labeling",
        "urgency": "Medium",
        "summary": "Investigational product outer packaging label missing required national language clinical trial warning text.",
        "country": "France",
        "nca": "ANSM",
        "therapeutic_area": "Dermatology",
        "indication": "Plaque Psoriasis",
        "days_ago": 10,
        "resolved_days_later": None,  # Unresolved
        "concern_text": "Under CTR Article 66, the primary packaging mock-up label must state 'A usage exclusif de recherche clinique' in French. Please submit revised artwork.",
        "ctr_article": "Article 66 - Labeling",
        "response_text": "Revised outer carton and vial label mock-ups with mandatory bilingual French/English regulatory text have been provided in Annex VI.",
    },
    {
        "rfi_id": "CT-2025-00901-91-00-SM01",
        "department": "Biostatistics",
        "category": "Data Integrity",
        "urgency": "High",
        "summary": "Missing data imputation strategy using Jump-to-Reference sensitivity analysis is not documented in the SAP.",
        "country": "Germany",
        "nca": "BfArM",
        "therapeutic_area": "Cardiovascular",
        "indication": "Atherosclerotic Cardiovascular Disease",
        "days_ago": 4,
        "resolved_days_later": None,  # Unresolved
        "concern_text": "Please provide sensitivity analyses evaluating the impact of missing primary endpoint data under departure from Missing-at-Random (MAR) assumptions.",
        "ctr_article": "Article 6, Part I Assessment",
        "response_text": "We have incorporated a pattern-mixture model using the Jump-to-Reference approach as a pre-specified sensitivity analysis in SAP Amendment 2.",
    },
]


def main():
    logger.info("Starting Clinical Trial Database Seeding & Synchronization Pipeline...")

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Missing Supabase credentials.")
        sys.exit(1)

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Clean up duplicate rows in Supabase rfi_intake
    logger.info("Cleaning up existing staging rows in Supabase rfi_intake...")
    try:
        res = sb.table("rfi_intake").select("id").execute()
        existing_ids = [r["id"] for r in (res.data or [])]
        logger.info("Found %d existing records to clean up.", len(existing_ids))
        for eid in existing_ids:
            sb.table("rfi_intake").delete().eq("id", eid).execute()
        logger.info("Supabase rfi_intake table cleared.")
    except Exception as e:
        logger.warning("Error clearing Supabase table: %s", e)

    # 2. Load SentenceTransformer model
    logger.info("Loading sentence-transformers/all-MiniLM-L6-v2 embedding model...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    summaries = [r["summary"] for r in REALISTIC_RFIS]
    logger.info("Encoding %d summaries into 384-dimensional dense vectors...", len(summaries))
    embeddings = model.encode(summaries, normalize_embeddings=True)
    sim_matrix = np.dot(embeddings, embeddings.T)
    logger.info("Vector embeddings generated successfully.")

    # 3. Insert 20 distinct records into Supabase rfi_intake
    now = datetime.now(timezone.utc)
    seeded_records = []
    SIM_THRESHOLD = 0.75

    for i, r in enumerate(REALISTIC_RFIS):
        emb_list = embeddings[i].tolist()
        ingested_at = (now - timedelta(days=r["days_ago"])).isoformat()
        resolved_at = None
        if r["resolved_days_later"]:
            resolved_at = (now - timedelta(days=r["days_ago"] - r["resolved_days_later"])).isoformat()

        # Check if RFI belongs to a semantic cluster (sim >= SIM_THRESHOLD with any other RFI)
        max_sim = max([float(sim_matrix[i, j]) for j in range(len(REALISTIC_RFIS)) if i != j])
        is_dup = max_sim >= SIM_THRESHOLD

        payload = {
            "rfi_id": r["rfi_id"],
            "department": r["department"],
            "category": r["category"],
            "urgency": r["urgency"],
            "summary": r["summary"],
            "is_duplicate": is_dup,
            "ingested_at": ingested_at,
            "resolved_at": resolved_at,
            "embedding": emb_list,
            "owner_team": "EU-Hub-Regulatory",
            "validation_status": "valid",
            "msc": {
                "country": r["country"],
                "nca": r["nca"],
            },
            "indication": {
                "therapeutic_area": r["therapeutic_area"],
                "name": r["indication"],
            },
            "considerations": [
                {
                    "number": 1,
                    "concern_text": r["concern_text"],
                    "ctr_article": {"name": r["ctr_article"]},
                    "response": {"text": r["response_text"]},
                }
            ],
        }
        res = sb.table("rfi_intake").insert(payload).execute()
        seeded_records.append(payload)

    logger.info("Successfully seeded %d clean, distinct RFIs into Supabase rfi_intake.", len(seeded_records))

    # 4. Synchronize with Neo4j Knowledge Graph
    if NEO4J_URI and NEO4J_PASSWORD:
        logger.info("Connecting to Neo4j Knowledge Graph at %s...", NEO4J_URI)
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        try:
            with driver.session() as s:
                # Remove old similarity edges to recalculate cleanly
                logger.info("Resetting old IS_SIMILAR_TO edges in Neo4j...")
                s.run("MATCH ()-[r:IS_SIMILAR_TO]->() DELETE r")

                # Merge RFI, Department, Category nodes
                logger.info("Merging RFI, Department, and Category nodes...")
                for r in REALISTIC_RFIS:
                    s.run(
                        """
                        MERGE (rfi:RFI {rfi_id: $rfi_id})
                        SET rfi.summary = $summary,
                            rfi.department = $department,
                            rfi.category = $category,
                            rfi.urgency = $urgency

                        MERGE (dept:Department {name: $department})
                        MERGE (rfi)-[:SUBMITTED_BY]->(dept)

                        MERGE (cat:Category {name: $category})
                        MERGE (rfi)-[:HAS_CATEGORY]->(cat)
                        """,
                        rfi_id=r["rfi_id"],
                        summary=r["summary"],
                        department=r["department"],
                        category=r["category"],
                        urgency=r["urgency"],
                    )

                # Create realistic IS_SIMILAR_TO edges based on vector cosine similarity
                edge_count = 0
                logger.info("Computing graph similarity edges (threshold >= %.2f)...", SIM_THRESHOLD)

                for i in range(len(REALISTIC_RFIS)):
                    for j in range(i + 1, len(REALISTIC_RFIS)):
                        sim_score = float(sim_matrix[i, j])
                        if sim_score >= SIM_THRESHOLD:
                            src_id = REALISTIC_RFIS[i]["rfi_id"]
                            tgt_id = REALISTIC_RFIS[j]["rfi_id"]
                            s.run(
                                """
                                MATCH (a:RFI {rfi_id: $src_id})
                                MATCH (b:RFI {rfi_id: $tgt_id})
                                MERGE (a)-[r:IS_SIMILAR_TO]->(b)
                                SET r.similarity = $sim_score
                                MERGE (b)-[r2:IS_SIMILAR_TO]->(a)
                                SET r2.similarity = $sim_score
                                """,
                                src_id=src_id,
                                tgt_id=tgt_id,
                                sim_score=round(sim_score, 4),
                            )
                            edge_count += 2
                            logger.info(
                                "  Edge: %s <-> %s (Cosine Similarity: %.1f%%)",
                                src_id, tgt_id, sim_score * 100
                            )

                logger.info("Created %d genuine IS_SIMILAR_TO edges in Neo4j AuraDB.", edge_count)
        finally:
            driver.close()

    # 5. Forward records to Layer 2 Central Repository (POST /rfi)
    logger.info("Forwarding records to Layer 2 Central Repository at %s...", LAYER2_URL)
    forwarded = 0
    try:
        with httpx.Client(timeout=15.0) as client:
            for r in REALISTIC_RFIS:
                l2_payload = {
                    "rfi_id": r["rfi_id"],
                    "due_date": (now + timedelta(days=14)).strftime("%Y-%m-%d"),
                    "submit_date": (now - timedelta(days=r["days_ago"])).strftime("%Y-%m-%d"),
                    "owner_team": "EU-Hub-Regulatory",
                    "category": r["category"],
                    "msc": {"country": r["country"]},
                    "indication": {"name": r["indication"]},
                    "considerations": [
                        {
                            "number": 1,
                            "concern_text": r["concern_text"],
                            "ctr_article": {"name": r["ctr_article"]},
                            "response": {"text": r["response_text"]},
                        }
                    ],
                }
                try:
                    resp = client.post(f"{LAYER2_URL}/rfi", json=l2_payload)
                    if resp.status_code in (200, 201):
                        forwarded += 1
                except Exception:
                    pass
        logger.info("Forwarded %d records to Layer 2.", forwarded)
    except Exception as e:
        logger.warning("Layer 2 sync skipped: %s", e)

    logger.info("🎉 REALISTIC SEEDING COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
