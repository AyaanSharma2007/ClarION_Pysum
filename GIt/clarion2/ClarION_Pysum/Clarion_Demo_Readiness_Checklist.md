# CLARION — DEMO READINESS CHECKLIST & FLOW
*What must exist, working, before demo day — and exactly how to walk judges through it.*

---

## 0. The one framing decision this whole document assumes

**No local LLM at demo time.** Per Section 13, run with `LLM_MODE=claude_api`. This is already an anticipated, sanctioned fallback in the bible itself — not a compromise you need to hide. State it plainly if asked (Q&A prep item #8): the architecture proves the confidentiality boundary is real and swappable; the demo runs on Claude API for extraction quality, and the self-hosted path is a config flag away, not a rebuild. **Do not claim the self-hosted/VPC-isolated path is live during the demo — that would be the one dishonest claim that actively contradicts Section 0's own rules.**

---

## 1. P0 — Must work live, no exceptions (the demo is not "ready" without these)

These are the items where, if broken or missing, the core pitch collapses — not just polish gaps.

### Data foundation
- [ ] **Seeded, realistic synthetic dataset already loaded** — do not rely on live-uploading a single RFI to populate the system. You need enough historical volume (dozens of RFIs, considerations, and responses across multiple MSCs/indications) that pattern detection and recommendations have something real to surface. A system with 3 seed records looks like a toy; one with realistic volume looks like a product.
- [ ] Synthetic data generated with **injected noise, not clean 1:1 correlations** — this is what makes the risk model's SHAP explanation defensible rather than tautological (see Section 14 discussion). Have your held-out accuracy number memorized.
- [ ] **`consideration_id` join-key contract verified** between Postgres and Neo4j — run the integration test (every ID resolves both directions) right before the demo, not days before.

### Core write path (Layer 2 + Governance, Section 7.1 / 6.1 / 6.2)
- [ ] `POST /rfi`, `POST /considerations`, `POST /responses` working end to end, with the mandated sequence intact: **Safety Gateway → OPA check → insert → embed → audit log write**
- [ ] Safety Gateway actually blocks a real injection attempt live — this needs a pre-scripted adversarial input ready to paste, not something you improvise
- [ ] `GATE-001` enforced at the write layer, not just the UI — you must be able to attempt a raw API bypass and show it rejected

### Governance ("the part that makes everything else trustworthy" — Section 2)
- [ ] Evidence Integrity Check panel showing all nine dimensions, inline on a record view (Section 6.3 / 12) — not a separate hidden page
- [ ] Hash-chained audit log fully wired (Section 10) — this is your single best "wow" moment if you also demo tamper detection
- [ ] Submission Gate state machine visibly enforced: Drafting → Pending Approval → Approved → Submitted, with a real human-approval click in the middle

### Intelligence layers (Connect / Predict / Recommend)
- [ ] `hybrid_search()` (8.5) working — pgvector similarity + Neo4j structural enrichment, combined, not just one half
- [ ] Section 8.6's core pattern query returning a real, interesting result from your seeded data (recurring MSC + Indication pairs)
- [ ] Risk engine (Section 9) returning per-category probabilities **with SHAP explanation attached** — never a bare number
- [ ] Recommender (Section 11) showing re-ranked results with visible `success_score`, not just similarity-sorted results

### Presentation surface
- [ ] At least one role-based dashboard fully functional (pick RA Clinical or EU Submission Hub — whichever maps best to your demo narrative)
- [ ] **Guided Demo Mode** (Section 12) built and rehearsed — this is explicitly designed as insurance against a flaky connection or a live-demo stumble; don't skip it as a "nice to have," it's the fallback that keeps a bad moment from becoming a bad demo

---

## 2. P1 — Strongly worth having, but the demo survives without them

- [ ] Louvain clustering / hub-article detection (Section 8.6's optional polish) — nice if it produces a visually compelling result, skip if it doesn't
- [ ] `policy_override` table/endpoint (Section 14.1) — good Q&A answer material even if not demoed live
- [ ] `extraction_correction` capture loop (Section 14.1) — same, good to describe, not essential to click through
- [ ] SimPy simulation module (Section 4/16 Phase C) — cut first if time is short, it's the least load-bearing piece of the whole architecture
- [ ] All four role-based dashboards (vs. just one) — one polished dashboard beats four half-built ones

---

## 3. Explicit non-negotiables for "looks ready" polish

These aren't features — they're the difference between "prototype that works" and "prototype that looks credible to a judge in 7 minutes."

- **No visible raw JSON, console errors, or 500s during the walkthrough.** Test the exact click path you'll perform, not just the underlying endpoints in isolation.
- **Realistic-looking data throughout** — real-sounding MSC names, indication names, CTR article references. "Test Test 123" as a concern_text breaks the illusion instantly.
- **The Evidence Integrity panel and Submission Gate states use consistent visual language** — a judge should recognize "this is the governed part" at a glance across every screen it appears on, not just once.
- **A backup screen-recording of the full flow**, in case live infra hiccups (per your own bible's own risk about the two-database join breaking live). Never let infrastructure risk be the reason the story doesn't land.
- **The Claude API fallback is never mentioned as an apology** — state it once, plainly, as the documented Section 13 fallback path, and move on.

---

## 4. Full Demo Flow (7 minutes)

### Minute 0–1 — Hook
*Show:* Landing page → "Start Guided Tour" (or go straight to Minute 1 if you're doing a live-narrated walkthrough instead of Guided Demo Mode).

*Say:* "Novo Nordisk submits roughly 650 Clinical Trial Applications a year, across up to 30 countries. Every one can generate a Request for Information — and right now those are answered one at a time, with no structured link between the one a reviewer in Spain raised last month and the nearly identical one raised in Germany today. This is Clarion — a regulatory memory platform that stops the same question being answered from scratch every time."

### Minute 1–2 — Capture → Connect
*Show:* Open an already-ingested RFI record. Point at a consideration's MSC/Indication/CTR Article tags — call out the `source: llm_extracted` badge explicitly.

*Say:* "This tagging is LLM-extracted and flagged as such — never presented as settled fact until a human confirms it."

*Show:* Run the pattern-detection query live (Section 8.6). Point at a real recurring MSC + Indication pair from your seeded data.

*Say:* "Spain and this indication have raised structurally similar concerns four times this year — that's a graph traversal, not a keyword search."

### Minute 2–3.5 — Predict
*Show:* Trigger the risk engine on a draft dossier. Show the per-category probability, then click into the SHAP explanation.

*Say:* "72% likelihood of a statistics-category RFI — never phrased as certainty, and never a black box. If you asked us right now for our held-out accuracy against baseline, it's [your real number] versus a [baseline]% naive baseline. We're not claiming this predicts real regulatory behavior yet — we're proving the explainability mechanism holds end to end."

*(This self-disclosed limitation, stated unprompted, is your highest-leverage 20 seconds in the whole demo — don't cut it under time pressure.)*

### Minute 3.5–4.5 — Recommend
*Show:* From the flagged risk category, click "find similar past responses." Point at the re-ranked list with visible success scores.

*Say:* "This is retrieve-then-enrich — pgvector finds semantically similar past considerations, Neo4j enriches with structure, then we re-rank by outcome, not just similarity. This response ranks higher because it actually worked — the MSC accepted it without a follow-up."

### Minute 4.5–6 — Govern
*Show:* Draft a response. Attempt a pre-scripted raw API call to mark it submitted without approval.

*Expected result:* Rejected — `GATE-001` violation.

*Say:* "The AI can draft. It cannot submit. Watch what happens if I try to bypass the interface entirely." *(Show the rejection.)* "Now the correct path—" *(Route through Submission Gate: Approve → Submitted.)* "A human authorized every step. That's logged."

*Show:* Evidence Integrity panel (all nine dimensions), then the audit trail.

*Optional, if time and rehearsal allow:* Tamper demo — modify a record directly in the DB, re-run `verify_chain()`, show the break. This is the single most memorable moment in the whole demo if you can land it cleanly; skip it entirely rather than risk it live if it's not rock-solid in rehearsal.

### Minute 6–7 — Close
*Say:* "Clarion isn't trying to replace validated GxP systems of record. It's solving one specific, quantified problem — 650 submissions a year with zero institutional memory between them — with a stack that takes two things seriously most AI compliance demos don't: it never lets a model make the submission decision, and it takes data confidentiality seriously enough to have a real self-hosted path, even though today's demo runs on Claude API for extraction quality. Thank you."

---

## 5. What specifically satisfies judges, from a user perspective, mapped to the rubric

**Innovation (25%)** — The moment that earns this is the SHAP-explained risk prediction plus the outcome-weighted recommender, not the governance layer. Judges see guardrails-around-an-LLM constantly this cycle; a genuinely predictive, explainable model tied to a real re-ranking signal is the differentiated part. Make sure this isn't rushed in favor of more governance screen time.

**Technical Implementation (25%)** — Satisfied by *showing the join actually work live* (hybrid_search visibly combining both databases) rather than describing the architecture. A specific number ("847 considerations, zero ID mismatches, verified this morning") lands harder than any diagram.

**Business Impact (20%)** — Satisfied by repeating the 650/year and 10–12 day SLA numbers at open and close, and by the pattern-detection moment landing as obviously useful rather than abstract — a judge should be able to say back to you "so it stops you answering the same question from scratch" without needing it re-explained.

**Feasibility (15%)** — Satisfied by *not* overclaiming. State the LLM_MODE=claude_api fallback plainly, name the synthetic-data caveat once, and don't imply the self-hosted path is running today. A team that volunteers its own limitations reads as more feasible than one that gets caught overselling.

**Presentation Quality (15%)** — Satisfied by the Guided Demo Mode existing as a visible safety net (even if you narrate live), zero visible errors during the walkthrough, and the unprompted SHAP-accuracy disclosure in Minute 2–3.5 — that single moment does more for credibility than any amount of slide polish.
