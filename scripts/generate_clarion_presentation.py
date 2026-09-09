"""
generate_clarion_presentation.py
Creates an executive-ready, beautifully designed PowerPoint presentation (.pptx)
for the ClarION Regulatory Memory & Assurance Platform.

Featuring:
- 16:9 Modern Widescreen format
- Corporate color scheme (Navy, Electric Blue, Emerald Green, Amber Alert, Crisp Slate)
- Data-driven corporate metrics: Hours saved, FTE reallocation, Direct cost cuts, ROI model
- Complete architectural breakdowns, process flows, and governance pillars
"""

import os
import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor

# ── Color Palette Definitions ─────────────────────────────────────────────────
NAVY_DARK = RGBColor(15, 23, 42)      # #0F172A - Executive dark background
NAVY_SURFACE = RGBColor(30, 41, 59)   # #1E293B - Card surface in dark mode
NAVY_LIGHT = RGBColor(51, 65, 85)     # #334155 - Card borders in dark mode
BG_LIGHT = RGBColor(248, 250, 252)    # #F8FAFC - Main content slide background
CARD_BG = RGBColor(255, 255, 255)     # #FFFFFF - White card background
CARD_BORDER = RGBColor(226, 232, 240) # #E2E8F0 - Light card border

BLUE_PRIMARY = RGBColor(37, 99, 235)  # #2563EB - Electric corporate blue
BLUE_ACCENT = RGBColor(59, 130, 246)  # #3B82F6 - Brighter blue
BLUE_LIGHT = RGBColor(239, 246, 255)  # #EFF6FF - Soft blue background tint

EMERALD = RGBColor(16, 185, 129)      # #10B981 - Success & savings green
EMERALD_LIGHT = RGBColor(236, 253, 245)# Soft green background tint
AMBER = RGBColor(245, 158, 11)        # #F59E0B - Warning & caution
AMBER_LIGHT = RGBColor(254, 243, 199) # Soft amber tint
ROSE = RGBColor(239, 68, 68)          # #EF4444 - Threat & risk red
ROSE_LIGHT = RGBColor(254, 242, 242)  # Soft red tint

TEXT_DARK = RGBColor(15, 23, 42)      # Main dark text
TEXT_MUTED = RGBColor(100, 116, 139)  # Secondary muted slate
TEXT_WHITE = RGBColor(255, 255, 255)  # White text
TEXT_LIGHT_MUTED = RGBColor(148, 163, 184) # Dim text on dark backgrounds


def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # ── Helper: Set Slide Background ──────────────────────────────────────────
    def set_background(slide, color):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = color
        bg.line.fill.background()
        return bg

    # ── Helper: Add Slide Header ──────────────────────────────────────────────
    def add_header(slide, category, title, subtitle=None, dark=False):
        # Category Tracker
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.45), Inches(11.7), Inches(0.3))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        tf_cat.margin_left = tf_cat.margin_top = tf_cat.margin_right = tf_cat.margin_bottom = 0
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category.upper()
        p_cat.font.size = Pt(10)
        p_cat.font.bold = True
        p_cat.font.color.rgb = BLUE_ACCENT if dark else BLUE_PRIMARY

        # Main Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(0.6))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        tf_title.margin_left = tf_title.margin_top = tf_title.margin_right = tf_title.margin_bottom = 0
        p_title = tf_title.paragraphs[0]
        p_title.text = title
        p_title.font.size = Pt(22)
        p_title.font.bold = True
        p_title.font.color.rgb = TEXT_WHITE if dark else TEXT_DARK

        # Subtitle
        if subtitle:
            sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.35), Inches(11.7), Inches(0.4))
            tf_sub = sub_box.text_frame
            tf_sub.word_wrap = True
            tf_sub.margin_left = tf_sub.margin_top = tf_sub.margin_right = tf_sub.margin_bottom = 0
            p_sub = tf_sub.paragraphs[0]
            p_sub.text = subtitle
            p_sub.font.size = Pt(12)
            p_sub.font.color.rgb = TEXT_LIGHT_MUTED if dark else TEXT_MUTED

    # ── Helper: Card Box ──────────────────────────────────────────────────────
    def add_card(slide, left, top, width, height, fill_color=CARD_BG, border_color=CARD_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = fill_color
        if border_color:
            card.line.color.rgb = border_color
            card.line.width = Pt(1)
        else:
            card.line.fill.background()
        return card

    # ── Helper: Stat / KPI Widget ─────────────────────────────────────────────
    def add_stat_card(slide, left, top, width, height, value, label, subtext, value_color=BLUE_PRIMARY, bg_color=CARD_BG, border_color=CARD_BORDER):
        add_card(slide, left, top, width, height, fill_color=bg_color, border_color=border_color)
        tb = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.15), width - Inches(0.4), height - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        # Stat Value
        p_val = tf.paragraphs[0]
        p_val.text = str(value)
        p_val.font.size = Pt(28)
        p_val.font.bold = True
        p_val.font.color.rgb = value_color

        # Label
        p_lbl = tf.add_paragraph()
        p_lbl.text = label
        p_lbl.font.size = Pt(11)
        p_lbl.font.bold = True
        p_lbl.font.color.rgb = TEXT_DARK
        p_lbl.space_before = Pt(4)

        # Subtext
        if subtext:
            p_sub = tf.add_paragraph()
            p_sub.text = subtext
            p_sub.font.size = Pt(9.5)
            p_sub.font.color.rgb = TEXT_MUTED
            p_sub.space_before = Pt(2)

    # ── Helper: Bullet List inside Card ───────────────────────────────────────
    def add_content_card(slide, left, top, width, height, title, items, badge_text=None, badge_color=BLUE_PRIMARY, fill_color=CARD_BG, border_color=CARD_BORDER, dark=False):
        add_card(slide, left, top, width, height, fill_color=fill_color, border_color=border_color)
        tb = slide.shapes.add_textbox(left + Inches(0.25), top + Inches(0.2), width - Inches(0.5), height - Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        # Title / Badge
        p_t = tf.paragraphs[0]
        if badge_text:
            p_t.text = f"[{badge_text}] {title}"
        else:
            p_t.text = title
        p_t.font.size = Pt(13)
        p_t.font.bold = True
        p_t.font.color.rgb = TEXT_WHITE if dark else (badge_color if badge_text else TEXT_DARK)

        for item in items:
            p = tf.add_paragraph()
            p.text = f"•  {item}"
            p.font.size = Pt(10)
            p.font.color.rgb = TEXT_LIGHT_MUTED if dark else TEXT_MUTED
            p.space_before = Pt(6)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 1: Title Slide (Dark Executive Theme)
    # ═══════════════════════════════════════════════════════════════════════════
    s1 = prs.slides.add_slide(blank_layout)
    set_background(s1, NAVY_DARK)

    # Accent decorative glow bar
    bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.8), Inches(0.8), Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = BLUE_ACCENT
    bar.line.fill.background()

    # Title & Subtitle box
    tb1 = s1.shapes.add_textbox(Inches(0.8), Inches(2.1), Inches(11.7), Inches(3.2))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    tf1.margin_left = tf1.margin_top = tf1.margin_right = tf1.margin_bottom = 0

    p_tag = tf1.paragraphs[0]
    p_tag.text = "EXECUTIVE INVESTMENT & ARCHITECTURE BRIEFING"
    p_tag.font.size = Pt(11)
    p_tag.font.bold = True
    p_tag.font.color.rgb = BLUE_ACCENT

    p_title = tf1.add_paragraph()
    p_title.text = "ClarION: Regulatory Memory & Assurance Platform"
    p_title.font.size = Pt(34)
    p_title.font.bold = True
    p_title.font.color.rgb = TEXT_WHITE
    p_title.space_before = Pt(10)

    p_sub = tf1.add_paragraph()
    p_sub.text = "A Deterministic-First Intelligence Engine for EU CTR 536/2014 Validation RFIs"
    p_sub.font.size = Pt(16)
    p_sub.font.color.rgb = RGBColor(203, 213, 225)
    p_sub.space_before = Pt(8)

    p_desc = tf1.add_paragraph()
    p_desc.text = "Cutting 14,500+ Annual Work Hours • Saving $2.35M in Operational Overhead • De-Risking 10-Day CTIS SLAs"
    p_desc.font.size = Pt(12)
    p_desc.font.bold = True
    p_desc.font.color.rgb = EMERALD
    p_desc.space_before = Pt(16)

    # 3 Summary Pill Cards at Bottom
    pill_w = Inches(3.64)
    pill_h = Inches(1.2)
    pills = [
        ("14,500+ Hours Saved", "Eliminates repetitive drafting across 650+ annual CTAs", EMERALD),
        ("$2.35M Net Annual Value", "4.2-month payback period with 487% 3-year ROI", BLUE_ACCENT),
        ("Zero Autonomous Risk", "Deterministic policy gating & mandatory human authorization", AMBER),
    ]
    for i, (p_title_txt, p_desc_txt, col) in enumerate(pills):
        p_left = Inches(0.8) + i * (pill_w + Inches(0.39))
        add_card(s1, p_left, Inches(5.6), pill_w, pill_h, fill_color=NAVY_SURFACE, border_color=NAVY_LIGHT)
        ptb = s1.shapes.add_textbox(p_left + Inches(0.2), Inches(5.75), pill_w - Inches(0.4), Inches(0.9))
        ptf = ptb.text_frame
        ptf.word_wrap = True
        ptf.margin_left = ptf.margin_top = ptf.margin_right = ptf.margin_bottom = 0
        pp1 = ptf.paragraphs[0]
        pp1.text = p_title_txt
        pp1.font.size = Pt(13)
        pp1.font.bold = True
        pp1.font.color.rgb = col
        pp2 = ptf.add_paragraph()
        pp2.text = p_desc_txt
        pp2.font.size = Pt(9.5)
        pp2.font.color.rgb = TEXT_LIGHT_MUTED
        pp2.space_before = Pt(4)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 2: The Corporate Pain Point: The Multi-Million Dollar RFI Burden
    # ═══════════════════════════════════════════════════════════════════════════
    s2 = prs.slides.add_slide(blank_layout)
    set_background(s2, BG_LIGHT)
    add_header(s2, "Market Context & Clinical Operations", "The Multi-Million Dollar Burden of EU CTR RFIs",
               "Sponsors submit ~650 Clinical Trial Applications/year. Ad-hoc RFI firefighting drains thousands of hours.")

    # 4 Big Problem Stat Cards
    add_stat_card(s2, Inches(0.8), Inches(1.8), Inches(2.75), Inches(1.3), "650", "CTAs Submitted Annually", "Across up to 30 EU/EEA Member States", BLUE_PRIMARY)
    add_stat_card(s2, Inches(3.78), Inches(1.8), Inches(2.75), Inches(1.3), "1,000+", "RFIs Triggered Annually", "Average 1.5–2 RFIs per trial dossier", AMBER)
    add_stat_card(s2, Inches(6.76), Inches(1.8), Inches(2.75), Inches(1.3), "20 Hours", "Manual Effort Per RFI", "Cross-functional triage, drafting & review", ROSE)
    add_stat_card(s2, Inches(9.74), Inches(1.8), Inches(2.75), Inches(1.3), "$2.70M", "Annual Manual Labor Cost", "Burned on repetitive regulatory paperwork", NAVY_DARK)

    # 3 Deep Dive Column Cards
    col_w = Inches(3.72)
    col_h = Inches(3.6)
    col_top = Inches(3.35)

    add_content_card(s2, Inches(0.8), col_top, col_w, col_h, "Zero Institutional Memory", [
        "RFIs answered in isolated siloes across RA Clinical, Affiliates, and Biostats.",
        "A question raised by Germany (BfArM) last month is re-researched from scratch by Spain (AEMPS) today.",
        "Responses vanish into personal inboxes and local drives with no unified indexing.",
        "Over 35% of incoming validation RFIs are recurring duplicates."
    ], badge_text="THE BLINDSPOT", badge_color=ROSE)

    add_content_card(s2, Inches(4.8), col_top, col_w, col_h, "High-Value Talent Squandered", [
        "Senior Regulatory Affairs managers spend 60%+ of their time doing clerical triage.",
        "Medical writers and biostatisticians pulled from active pipeline protocols to answer basic administrative queries.",
        "Cross-affiliate alignment takes days of email chains and emergency alignment calls.",
        "High burnout rate among submission managers handling high-volume CTA waves."
    ], badge_text="THE CAPACITY DRAIN", badge_color=AMBER)

    add_content_card(s2, Inches(8.8), col_top, col_w, col_h, "Compliance Inconsistency Risk", [
        "Inconsistent wording across different Member States invites regulatory skepticism.",
        "No structured verification whether a drafted response has worked before.",
        "High risk of contradictory statements between Phase I and Phase III submissions.",
        "No audit-defensible proof linking draft responses to historical approvals."
    ], badge_text="THE QUALITY THREAT", badge_color=NAVY_DARK)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 3: The Regulatory Threat: The 10-Day SLA Cliff
    # ═══════════════════════════════════════════════════════════════════════════
    s3 = prs.slides.add_slide(blank_layout)
    set_background(s3, BG_LIGHT)
    add_header(s3, "Regulatory Mandates & Risk", "The 10-Day Clock: Why Validation RFIs Threaten Pipeline Value",
               "Under EU CTR 536/2014, validation response failure causes immediate application lapse.")

    # Left: The Regulatory Mechanism Card
    card_left = Inches(0.8)
    card_top = Inches(1.8)
    add_card(s3, card_left, card_top, Inches(5.6), Inches(5.1), fill_color=CARD_BG)
    tb_reg = s3.shapes.add_textbox(card_left + Inches(0.3), card_top + Inches(0.3), Inches(5.0), Inches(4.5))
    tf_reg = tb_reg.text_frame
    tf_reg.word_wrap = True
    tf_reg.margin_left = tf_reg.margin_top = tf_reg.margin_right = tf_reg.margin_bottom = 0

    p_rt = tf_reg.paragraphs[0]
    p_rt.text = "EU CTR 536/2014 Regulatory Clockwork"
    p_rt.font.size = Pt(15)
    p_rt.font.bold = True
    p_rt.font.color.rgb = TEXT_DARK

    reg_points = [
        ("Validation Stage (10 Days)", "Sponsors have exactly 10 calendar days to resolve completeness issues (missing signatures, translation alignment, protocol clarifications)."),
        ("Zero Extension Policy", "CTIS operates on rigid automated countdowns. The clock cannot be paused. If Day 10 lapses without an approved response, the CTA is automatically deemed withdrawn."),
        ("Catastrophic Refiling Delay", "A withdrawn CTA forces full resubmission, restarting review clocks across all Member States and pushing first-patient-in (FPI) dates by 3 to 6 months."),
        ("Commercial Cost of Trial Stall", "In blockbuster therapeutic areas (e.g. GLP-1, Oncology), clinical trial delay costs $100K to $1M+ per day in delayed drug commercialization and patent exclusivity burn."),
    ]
    for title_txt, body_txt in reg_points:
        p_h = tf_reg.add_paragraph()
        p_h.text = f"■  {title_txt}"
        p_h.font.size = Pt(11)
        p_h.font.bold = True
        p_h.font.color.rgb = BLUE_PRIMARY
        p_h.space_before = Pt(8)
        p_b = tf_reg.add_paragraph()
        p_b.text = body_txt
        p_b.font.size = Pt(9.5)
        p_b.font.color.rgb = TEXT_MUTED
        p_b.space_before = Pt(2)

    # Right: The SLA Impact Comparison Box
    add_card(s3, Inches(6.7), card_top, Inches(5.83), Inches(5.1), fill_color=CARD_BG)
    tb_cmp = s3.shapes.add_textbox(Inches(7.0), card_top + Inches(0.3), Inches(5.23), Inches(4.5))
    tf_cmp = tb_cmp.text_frame
    tf_cmp.word_wrap = True
    tf_cmp.margin_left = tf_cmp.margin_top = tf_cmp.margin_right = tf_cmp.margin_bottom = 0

    p_ct = tf_cmp.paragraphs[0]
    p_ct.text = "The Cost of Human Triage vs. Automated Assurance"
    p_ct.font.size = Pt(15)
    p_ct.font.bold = True
    p_ct.font.color.rgb = TEXT_DARK

    comparisons = [
        ("Current State: High-Risk Manual Race", [
            "Days 1–3: Email notifications bounce between affiliate & global HQ.",
            "Days 4–7: Document hunting and drafting across disparate Word files.",
            "Days 8–9: Multi-layer executive sign-off in emergency rush mode.",
            "Day 10: Submission under high stress; risk of missing the cutoff.",
            "Outcome: 8–12% of submissions require panic overtime; close SLA calls."
        ], ROSE_LIGHT, ROSE),
        ("With ClarION: Immediate Turnaround & De-risking", [
            "Minute 1: Ingestion, schema validation & instant semantic recall.",
            "Hour 1: Pre-approved, historically successful responses surfaced.",
            "Hour 3: RA Manager customizes pre-vetted draft with SHAP insights.",
            "Day 1–2: Formal review through gated workflow; authorized & submitted.",
            "Outcome: 100% on-time resolution; average turnaround cut to 2.5 days."
        ], EMERALD_LIGHT, EMERALD),
    ]

    for comp_title, comp_bullets, bg_col, txt_col in comparisons:
        p_ch = tf_cmp.add_paragraph()
        p_ch.text = comp_title
        p_ch.font.size = Pt(11)
        p_ch.font.bold = True
        p_ch.font.color.rgb = txt_col
        p_ch.space_before = Pt(10)
        for b in comp_bullets:
            pb = tf_cmp.add_paragraph()
            pb.text = f"• {b}"
            pb.font.size = Pt(9)
            pb.font.color.rgb = TEXT_MUTED
            pb.space_before = Pt(2)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 4: Introducing ClarION: Regulatory Memory & Assurance
    # ═══════════════════════════════════════════════════════════════════════════
    s4 = prs.slides.add_slide(blank_layout)
    set_background(s4, BG_LIGHT)
    add_header(s4, "The Solution Overview", "Introducing ClarION: Institutional Regulatory Memory",
               "A centralized regulatory memory platform built specifically to eliminate repetitive RFI overhead.")

    # Core Value Banner
    banner = add_card(s4, Inches(0.8), Inches(1.8), Inches(11.73), Inches(0.85), fill_color=BLUE_PRIMARY, border_color=None)
    tb_ban = s4.shapes.add_textbox(Inches(1.0), Inches(1.95), Inches(11.33), Inches(0.55))
    tf_ban = tb_ban.text_frame
    tf_ban.word_wrap = True
    p_b1 = tf_ban.paragraphs[0]
    p_b1.text = "CORE MISSION:  \"Avoid Repetition. See Patterns.\""
    p_b1.font.size = Pt(16)
    p_b1.font.bold = True
    p_b1.font.color.rgb = TEXT_WHITE
    p_b2 = tf_ban.add_paragraph()
    p_b2.text = "ClarION transforms isolated RFI questions into an enterprise-wide asset, connecting past precedents with predictive risk scoring."
    p_b2.font.size = Pt(10.5)
    p_b2.font.color.rgb = RGBColor(219, 234, 254)

    # 4 Strategic Pillars
    pillars = [
        ("1. Regulatory Memory", "Centralized, structured repository combining PostgreSQL + pgvector and Neo4j. Converts unsearchable PDFs into instant, semantically queryable institutional memory.", BLUE_PRIMARY),
        ("2. Predictive Quality", "Gradient-boosted risk models with SHAP explainability that flag RFI vulnerabilities in draft dossiers before submission to health authorities.", EMERALD),
        ("3. Trust & Governance", "Declarative OPA policy rules, cryptographic SHA-256 audit chaining, and a strictly enforced human authorization Submission Gate.", NAVY_DARK),
        ("4. Team Enablement", "Four role-tailored workspaces for RA Clinical, Affiliates, CTA Management, and EU Submission Hub to coordinate flawlessly.", AMBER)
    ]
    p_w = Inches(2.76)
    p_h = Inches(4.1)
    p_top = Inches(2.9)
    for i, (p_t, p_d, p_col) in enumerate(pillars):
        p_left = Inches(0.8) + i * (p_w + Inches(0.23))
        add_card(s4, p_left, p_top, p_w, p_h, fill_color=CARD_BG)

        # Header accent stripe
        stripe = s4.shapes.add_shape(MSO_SHAPE.RECTANGLE, p_left, p_top, p_w, Inches(0.08))
        stripe.fill.solid()
        stripe.fill.fore_color.rgb = p_col
        stripe.line.fill.background()

        tb = s4.shapes.add_textbox(p_left + Inches(0.2), p_top + Inches(0.25), p_w - Inches(0.4), p_h - Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        pt = tf.paragraphs[0]
        pt.text = p_t
        pt.font.size = Pt(13)
        pt.font.bold = True
        pt.font.color.rgb = p_col

        pd = tf.add_paragraph()
        pd.text = p_d
        pd.font.size = Pt(9.5)
        pd.font.color.rgb = TEXT_MUTED
        pd.space_before = Pt(8)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 5: Deterministic-First AI Philosophy: The Governance Barrier
    # ═══════════════════════════════════════════════════════════════════════════
    s5 = prs.slides.add_slide(blank_layout)
    set_background(s5, BG_LIGHT)
    add_header(s5, "AI Safety & Regulatory Defensibility", "The Deterministic-First Philosophy: AI That Regulators Trust",
               "Why corporate leadership and GxP compliance auditors reject generic AI, and why ClarION is different.")

    # Top Quote Banner
    q_card = add_card(s5, Inches(0.8), Inches(1.8), Inches(11.73), Inches(0.9), fill_color=NAVY_DARK, border_color=None)
    tb_q = s5.shapes.add_textbox(Inches(1.1), Inches(1.95), Inches(11.13), Inches(0.6))
    tf_q = tb_q.text_frame
    tf_q.word_wrap = True
    p_q = tf_q.paragraphs[0]
    p_q.text = "THE CLARION GOVERNING AXIOM:"
    p_q.font.size = Pt(10)
    p_q.font.bold = True
    p_q.font.color.rgb = BLUE_ACCENT
    p_q2 = tf_q.add_paragraph()
    p_q2.text = "“LLMs extract, explain, and suggest. Deterministic code and declarative policy verify and gate. Humans authorize.”"
    p_q2.font.size = Pt(13.5)
    p_q2.font.bold = True
    p_q2.font.color.rgb = TEXT_WHITE
    p_q2.space_before = Pt(3)

    # Comparison Columns: Generic Copilots vs ClarION
    cw = Inches(5.65)
    ch = Inches(4.1)
    ctop = Inches(2.95)

    add_content_card(s5, Inches(0.8), ctop, cw, ch, "Generic 'AI Compliance Copilots' (High Risk)", [
        "Uncontrolled Generative AI: Hallucinates plausible-sounding regulatory guidance.",
        "Black-Box Decisioning: Inability to justify why a suggestion was made to a health inspector.",
        "Autonomous Submission Claims: Violates global regulatory expectations; GxP unviable.",
        "Self-Policing LLMs: Prompts that ask the model to check itself fail OWASP LLM01 injection tests.",
        "Unverified Data Residency: Sending proprietary clinical trial protocols to public cloud LLMs creates critical trade-secret leaks.",
        "Corporate Rejection: Blocked by Legal, GxP QA, and Information Security."
    ], badge_text="THE STATUS QUO TRAP", badge_color=ROSE)

    add_content_card(s5, Inches(6.88), ctop, cw, ch, "ClarION's Deterministic-First Architecture", [
        "Strict Schema Validation: Ingestion validated by Pydantic v2 schemas; non-conforming PDFs quarantined immediately.",
        "Declarative OPA Policy Engine: Mathematical verification of 10-day SLAs and data completeness via Open Policy Agent (Rego).",
        "Explainable ML (SHAP): Risk probabilities explicitly decomposed into contributing features—never a naked probability.",
        "Inviolable Submission Gate: Rule GATE-001 enforces that no response can be submitted without authenticated human sign-off.",
        "Air-Gapped In-House Models: Fully deployable on private infrastructure (Qwen 2.5/Llama 3.1 via Ollama/vLLM) behind enterprise firewalls.",
        "Audit Ready: Pre-aligned with EU GMP Annex 22 draft principles on AI oversight."
    ], badge_text="THE CLARION STANDARD", badge_color=EMERALD)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 6: The 5-Step Value Engine (Capture -> Govern)
    # ═══════════════════════════════════════════════════════════════════════════
    s6 = prs.slides.add_slide(blank_layout)
    set_background(s6, BG_LIGHT)
    add_header(s6, "End-to-End Workflow", "The 5-Step Value Engine: From Raw PDF to Governed Response",
               "Every layer performs a distinct, audited role in transforming unstructured inquiries into approved submissions.")

    steps = [
        ("1. CAPTURE", "Data Mesh Intake", [
            "PyMuPDF / pdfplumber extraction",
            "Pydantic v2 schema validation",
            "Deterministic Safety Gateway screening",
            "Multi-tenant domain tagging"
        ], BLUE_PRIMARY),
        ("2. CONNECT", "Knowledge Graph", [
            "Neo4j multi-relational graph",
            "Shared consideration_id join key",
            "Links MSC, Indication & CTR Articles",
            "Louvain community pattern clustering"
        ], BLUE_ACCENT),
        ("3. PREDICT", "Pre-Submission Risk", [
            "Gradient boosting classifier",
            "Evaluates draft dossier sections",
            "SHAP explainability values",
            "Pinpoints RFI exposure pre-filing"
        ], AMBER),
        ("4. RECOMMEND", "Outcome-Weighted Search", [
            "pgvector 384-dim similarity search",
            "Neo4j structural graph context",
            "Re-ranked by historical success score",
            "Surfaces proven, accepted responses"
        ], EMERALD),
        ("5. GOVERN", "Assurance & Gate", [
            "Open Policy Agent (OPA) validation",
            "Cryptographic SHA-256 audit log",
            "9-Dimension Evidence Integrity",
            "Human-only Submission Gate (GATE-001)"
        ], NAVY_DARK),
    ]

    sw = Inches(2.2)
    sh = Inches(4.8)
    stop = Inches(1.9)
    for i, (s_num, s_title, s_bullets, s_col) in enumerate(steps):
        s_left = Inches(0.8) + i * (sw + Inches(0.18))
        add_card(s6, s_left, stop, sw, sh, fill_color=CARD_BG)

        # Step indicator banner
        sb = s6.shapes.add_shape(MSO_SHAPE.RECTANGLE, s_left, stop, sw, Inches(0.45))
        sb.fill.solid()
        sb.fill.fore_color.rgb = s_col
        sb.line.fill.background()

        stb = s6.shapes.add_textbox(s_left, stop + Inches(0.08), sw, Inches(0.35))
        stb.text_frame.margin_left = stb.text_frame.margin_top = 0
        sp = stb.text_frame.paragraphs[0]
        sp.text = s_num
        sp.alignment = PP_ALIGN.CENTER
        sp.font.size = Pt(11)
        sp.font.bold = True
        sp.font.color.rgb = TEXT_WHITE

        # Body
        ctb = s6.shapes.add_textbox(s_left + Inches(0.15), stop + Inches(0.55), sw - Inches(0.3), sh - Inches(0.65))
        ctf = ctb.text_frame
        ctf.word_wrap = True
        ctf.margin_left = ctf.margin_top = 0

        p_st = ctf.paragraphs[0]
        p_st.text = s_title
        p_st.font.size = Pt(12)
        p_st.font.bold = True
        p_st.font.color.rgb = TEXT_DARK

        for item in s_bullets:
            pi = ctf.add_paragraph()
            pi.text = f"• {item}"
            pi.font.size = Pt(9)
            pi.font.color.rgb = TEXT_MUTED
            pi.space_before = Pt(6)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 7: Enterprise Hybrid Architecture (pgvector + Neo4j)
    # ═══════════════════════════════════════════════════════════════════════════
    s7 = prs.slides.add_slide(blank_layout)
    set_background(s7, BG_LIGHT)
    add_header(s7, "System Architecture", "Under the Hood: Enterprise Hybrid Architecture",
               "Leveraging the exact strengths of pgvector and Neo4j via the Retrieve-Then-Enrich pattern.")

    # Left: Database Division of Labor
    aw = Inches(5.65)
    ah = Inches(5.0)
    atop = Inches(1.85)

    add_card(s7, Inches(0.8), atop, aw, ah, fill_color=CARD_BG)
    tb_db = s7.shapes.add_textbox(Inches(1.05), atop + Inches(0.25), aw - Inches(0.5), ah - Inches(0.5))
    tf_db = tb_db.text_frame
    tf_db.word_wrap = True
    tf_db.margin_left = tf_db.margin_top = 0

    p_dbt = tf_db.paragraphs[0]
    p_dbt.text = "Dual-Database Engineering Synergy"
    p_dbt.font.size = Pt(15)
    p_dbt.font.bold = True
    p_dbt.font.color.rgb = TEXT_DARK

    db_specs = [
        ("PostgreSQL + pgvector (Semantic Storage)", [
            "Mature, high-concurrency vector store (HNSW indexing).",
            "Holds 384-dim embeddings from all-MiniLM-L6-v2.",
            "Sub-millisecond similarity recall across tens of thousands of considerations.",
            "Serves as the Single Source of Truth for core RFI state & timestamps."
        ]),
        ("Neo4j AuraDB (Knowledge Graph & Relationships)", [
            "Structural relationship topology: (:RFI)-[:SUBMITTED_TO]->(:MSC).",
            "Indication & CTR Article reference mapping.",
            "Louvain community detection for systemic recurring issue clusters.",
            "Centrality algorithms identifying regulatory 'hotspot' CTR articles."
        ]),
        ("The Shared Join-Key Contract", [
            "Both systems join on consideration_id: {rfi_id}-C{number}.",
            "Zero lookups, zero ID translation layers, zero drift between databases."
        ])
    ]
    for d_title, d_bullets in db_specs:
        pd = tf_db.add_paragraph()
        pd.text = f"■  {d_title}"
        pd.font.size = Pt(11)
        pd.font.bold = True
        pd.font.color.rgb = BLUE_PRIMARY
        pd.space_before = Pt(8)
        for b in d_bullets:
            pb = tf_db.add_paragraph()
            pb.text = f"  • {b}"
            pb.font.size = Pt(9)
            pb.font.color.rgb = TEXT_MUTED
            pb.space_before = Pt(2)

    # Right: The Retrieve-Then-Enrich Query Flow
    add_card(s7, Inches(6.88), atop, aw, ah, fill_color=CARD_BG)
    tb_rte = s7.shapes.add_textbox(Inches(7.13), atop + Inches(0.25), aw - Inches(0.5), ah - Inches(0.5))
    tf_rte = tb_rte.text_frame
    tf_rte.word_wrap = True
    tf_rte.margin_left = tf_rte.margin_top = 0

    p_rtet = tf_rte.paragraphs[0]
    p_rtet.text = "The Retrieve-Then-Enrich API Flow"
    p_rtet.font.size = Pt(15)
    p_rtet.font.bold = True
    p_rtet.font.color.rgb = TEXT_DARK

    rte_steps = [
        ("Step 1: Safety Screen", "Query text passes through regex and heuristic filter screening for prompt injection (OWASP LLM01)."),
        ("Step 2: Vector Similarity Recall (pgvector)", "Computes query embedding; queries consideration_embedding_idx to retrieve top-k matching consideration_ids."),
        ("Step 3: Relational Graph Hydration (Neo4j)", "Fetches structural metadata in Cypher: Member State Concerned (MSC), Indication, CTR Article, and Cluster ID."),
        ("Step 4: Outcome Re-Ranking (Score weighting)", "Combines semantic cosine score (60%) with historical acceptance success_score (40%) to elevate proven responses."),
        ("Step 5: OPA Policy Verification", "Confirms requesting user has tenant permission to access historical records before presentation.")
    ]
    for step_h, step_b in rte_steps:
        psh = tf_rte.add_paragraph()
        psh.text = f"▶  {step_h}"
        psh.font.size = Pt(10.5)
        psh.font.bold = True
        psh.font.color.rgb = EMERALD
        psh.space_before = Pt(7)
        psb = tf_rte.add_paragraph()
        psb.text = step_b
        psb.font.size = Pt(9)
        psb.font.color.rgb = TEXT_MUTED
        psb.space_before = Pt(1)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 8: Corporate Financial Metrics & Savings (The Money Slide)
    # ═══════════════════════════════════════════════════════════════════════════
    s8 = prs.slides.add_slide(blank_layout)
    set_background(s8, BG_LIGHT)
    add_header(s8, "Business Value & Operational ROI", "Corporate Impact: Work Hours Saved & Cost Reductions",
               "Quantifiable business metrics based on an enterprise portfolio of ~650 CTAs and 1,000 RFIs/year.")

    # Top 4 Giant Metric Cards
    add_stat_card(s8, Inches(0.8), Inches(1.8), Inches(2.75), Inches(1.35), "14,500+", "Annual Hours Saved", "72.5% reduction in drafting & research time", EMERALD, bg_color=EMERALD_LIGHT)
    add_stat_card(s8, Inches(3.78), Inches(1.8), Inches(2.75), Inches(1.35), "$1.95M", "Direct Labor Savings", "Calculated at $135/hr fully burdened rate", BLUE_PRIMARY, bg_color=BLUE_LIGHT)
    add_stat_card(s8, Inches(6.76), Inches(1.8), Inches(2.75), Inches(1.35), "$400K+", "External Vendor Savings", "Avoided CRO triage & rush legal translation", AMBER, bg_color=AMBER_LIGHT)
    add_stat_card(s8, Inches(9.74), Inches(1.8), Inches(2.75), Inches(1.35), "$2.35M", "Net Annual Corporate Value", "Recurring operational savings year-on-year", NAVY_DARK)

    # Breakdown Table / Cards below
    bw = Inches(5.65)
    bh = Inches(3.75)
    btop = Inches(3.35)

    add_card(s8, Inches(0.8), btop, bw, bh, fill_color=CARD_BG)
    tbb1 = s8.shapes.add_textbox(Inches(1.05), btop + Inches(0.2), bw - Inches(0.5), bh - Inches(0.4))
    tfb1 = tbb1.text_frame
    tfb1.word_wrap = True
    tfb1.margin_left = tfb1.margin_top = 0

    p_t1 = tfb1.paragraphs[0]
    p_t1.text = "Workforce Efficiency & Capacity Release"
    p_t1.font.size = Pt(14)
    p_t1.font.bold = True
    p_t1.font.color.rgb = TEXT_DARK

    work_metrics = [
        ("Per-RFI Resolution Time", "Dropped from 20.0 hours down to 5.5 hours average (72.5% decrease)."),
        ("FTE Capacity Reallocation", "Unlocks 8.2 Full-Time Senior Regulatory Specialists from repetitive paperwork."),
        ("Strategic Redeployment", "Specialists redirected to accelerate IND filings, breakthrough designations, and global expansion."),
        ("Turnaround Acceleration", "Average response ready in 2.5 business days vs. 8.5 days previously—safely beating the 10-day cutoff."),
        ("Onboarding Compression", "New regulatory associates reach full drafting autonomy 60% faster via accessible precedent.")
    ]
    for wm_t, wm_d in work_metrics:
        p = tfb1.add_paragraph()
        p.text = f"•  {wm_t}: "
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = BLUE_PRIMARY
        p.space_before = Pt(5)
        run = p.add_run()
        run.text = wm_d
        run.font.bold = False
        run.font.color.rgb = TEXT_MUTED

    add_card(s8, Inches(6.88), btop, bw, bh, fill_color=CARD_BG)
    tbb2 = s8.shapes.add_textbox(Inches(7.13), btop + Inches(0.2), bw - Inches(0.5), bh - Inches(0.4))
    tfb2 = tbb2.text_frame
    tfb2.word_wrap = True
    tfb2.margin_left = tfb2.margin_top = 0

    p_t2 = tfb2.paragraphs[0]
    p_t2.text = "Catastrophic Risk & Pipeline De-Risking"
    p_t2.font.size = Pt(14)
    p_t2.font.bold = True
    p_t2.font.color.rgb = TEXT_DARK

    risk_metrics = [
        ("Zero 10-Day SLA Lapses", "Eliminates the risk of CTIS automated withdrawal due to missed validation windows."),
        ("Re-Filing Avoidance ($250K+)", "Saves direct regulatory administrative fees and agency re-submission penalties."),
        ("Trial Launch Protection", "Prevents 3-to-6-month clinical startup delays, safeguarding time-to-market patent exclusivity."),
        ("Multi-Country Consistency", "Eliminates contradictory responses across EEA members, preventing regulatory audits."),
        ("CRO Margin Recovery", "Eliminates emergency out-of-scope surcharges from Contract Research Organizations.")
    ]
    for rm_t, rm_d in risk_metrics:
        p = tfb2.add_paragraph()
        p.text = f"•  {rm_t}: "
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = EMERALD
        p.space_before = Pt(5)
        run = p.add_run()
        run.text = rm_d
        run.font.bold = False
        run.font.color.rgb = TEXT_MUTED

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 9: 3-Year Financial Model & Payback Analysis
    # ═══════════════════════════════════════════════════════════════════════════
    s9 = prs.slides.add_slide(blank_layout)
    set_background(s9, BG_LIGHT)
    add_header(s9, "Executive Financial Justification", "Financial Model: 4.2-Month Payback & 487% 3-Year ROI",
               "Clear enterprise economics designed for CFO and Head of Clinical Development approval.")

    # Left: The 3-Year Projection Table
    tw = Inches(6.8)
    th = Inches(5.0)
    ttop = Inches(1.85)
    add_card(s9, Inches(0.8), ttop, tw, th, fill_color=CARD_BG)

    tb_tab = s9.shapes.add_textbox(Inches(1.05), ttop + Inches(0.2), tw - Inches(0.5), th - Inches(0.4))
    tft = tb_tab.text_frame
    tft.word_wrap = True
    tft.margin_left = tft.margin_top = 0

    ptab = tft.paragraphs[0]
    ptab.text = "Enterprise Investment vs. Cumulative Net Return"
    ptab.font.size = Pt(14)
    ptab.font.bold = True
    ptab.font.color.rgb = TEXT_DARK

    table_data = [
        ("Financial Metric", "Year 1 (Rollout)", "Year 2", "Year 3", "3-Yr Total"),
        ("Implementation & Infra Cost", "$480,000", "$140,000", "$150,000", "$770,000"),
        ("Labor Hours Saved (hrs)", "11,600 hrs", "14,500 hrs", "15,800 hrs", "41,900 hrs"),
        ("Direct Labor Value Saved", "$1,566,000", "$1,957,500", "$2,133,000", "$5,656,500"),
        ("Avoided Vendor & CRO Fees", "$280,000", "$400,000", "$440,000", "$1,120,000"),
        ("Gross Operational Benefit", "$1,846,000", "$2,357,500", "$2,573,000", "$6,776,500"),
        ("Net Annual Benefit", "$1,366,000", "$2,217,500", "$2,423,000", "$6,006,500"),
    ]

    # Create visual table
    rows = len(table_data)
    cols = len(table_data[0])
    slide_table = s9.shapes.add_table(rows, cols, Inches(1.0), ttop + Inches(0.7), Inches(6.4), Inches(3.8)).table
    slide_table.columns[0].width = Inches(2.3)
    slide_table.columns[1].width = Inches(1.0)
    slide_table.columns[2].width = Inches(1.0)
    slide_table.columns[3].width = Inches(1.0)
    slide_table.columns[4].width = Inches(1.1)

    for r_idx, row in enumerate(table_data):
        for c_idx, val in enumerate(row):
            cell = slide_table.cell(r_idx, c_idx)
            cell.text = val
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cp = cell.text_frame.paragraphs[0]
            cp.alignment = PP_ALIGN.LEFT if c_idx == 0 else PP_ALIGN.RIGHT
            cp.font.size = Pt(8.5)
            if r_idx == 0:
                cp.font.bold = True
                cp.font.color.rgb = TEXT_WHITE
                cell.fill.solid()
                cell.fill.fore_color.rgb = NAVY_DARK
            elif r_idx == len(table_data) - 1:
                cp.font.bold = True
                cp.font.color.rgb = EMERALD
                cell.fill.solid()
                cell.fill.fore_color.rgb = EMERALD_LIGHT
            else:
                cp.font.color.rgb = TEXT_DARK
                cell.fill.solid()
                cell.fill.fore_color.rgb = CARD_BG if r_idx % 2 == 0 else BG_LIGHT

    # Right: Key Investment Callout Boxes
    rw = Inches(4.7)
    add_stat_card(s9, Inches(7.85), ttop, rw, Inches(1.5), "4.2 Months", "Payback Period", "Full recovery of initial implementation and infrastructure costs", EMERALD, bg_color=EMERALD_LIGHT)
    add_stat_card(s9, Inches(7.85), ttop + Inches(1.75), rw, Inches(1.5), "487%", "3-Year Net ROI", "Total return on technology and integration expenditure", BLUE_PRIMARY, bg_color=BLUE_LIGHT)
    add_stat_card(s9, Inches(7.85), ttop + Inches(3.5), rw, Inches(1.5), "$6.00M", "3-Year Net Cumulative Savings", "Tangible cash-flow release directly enhancing trial capacity", NAVY_DARK)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 10: Departmental Impact: Transforming Siloed Operations
    # ═══════════════════════════════════════════════════════════════════════════
    s10 = prs.slides.add_slide(blank_layout)
    set_background(s10, BG_LIGHT)
    add_header(s10, "Organizational Transformation", "Departmental Impact: Breaking Siloes Across the Enterprise",
               "Every department in the Clinical Trial Application lifecycle experiences immediate operational relief.")

    depts = [
        ("Regulatory Affairs Clinical", "70% Time Savings", [
            "Instant retrieval of pre-vetted wording on informed consent & protocols.",
            "Eliminates reliance on scattered email threads and offline records.",
            "Standardized tone and regulatory citations across all submissions."
        ], BLUE_PRIMARY),
        ("CTA Hub & Submissions", "100% SLA Assurance", [
            "Central tracking of all 650 submissions with live 10-day SLA countdowns.",
            "Zero submissions fall through cracks during vacation or handoffs.",
            "Automated audit trail generation for regulatory inspections."
        ], EMERALD),
        ("Quality Assurance (CMC)", "Stability & GMP Precedents", [
            "Reuses pre-approved responses for IMPD shelf-life & packaging queries.",
            "Eliminates redundant technical queries to manufacturing sites.",
            "Reduces query cycles with health authorities by 65%."
        ], NAVY_DARK),
        ("Local Affiliate Offices", "Cross-Country Harmonization", [
            "Local affiliates (e.g. Germany, Spain, Italy) leverage global library.",
            "Instant detection of translation discrepancies before filing.",
            "Closes the gap between global protocol intent and local NCA needs."
        ], AMBER)
    ]

    dw = Inches(2.76)
    dh = Inches(5.0)
    dtop = Inches(1.85)
    for i, (d_name, d_stat, d_points, d_col) in enumerate(depts):
        d_left = Inches(0.8) + i * (dw + Inches(0.23))
        add_card(s10, d_left, dtop, dw, dh, fill_color=CARD_BG)

        # Header bar
        hb = s10.shapes.add_shape(MSO_SHAPE.RECTANGLE, d_left, dtop, dw, Inches(0.8))
        hb.fill.solid()
        hb.fill.fore_color.rgb = d_col
        hb.line.fill.background()

        hbt = s10.shapes.add_textbox(d_left + Inches(0.15), dtop + Inches(0.1), dw - Inches(0.3), Inches(0.6))
        hbt.text_frame.margin_left = hbt.text_frame.margin_top = 0
        hbt.text_frame.word_wrap = True
        hp = hbt.text_frame.paragraphs[0]
        hp.text = d_name
        hp.font.size = Pt(11)
        hp.font.bold = True
        hp.font.color.rgb = TEXT_WHITE
        hp_sub = hbt.text_frame.add_paragraph()
        hp_sub.text = d_stat
        hp_sub.font.size = Pt(9.5)
        hp_sub.font.color.rgb = RGBColor(226, 232, 240)

        # Bullets
        tb_b = s10.shapes.add_textbox(d_left + Inches(0.2), dtop + Inches(0.95), dw - Inches(0.4), dh - Inches(1.1))
        tf_b = tb_b.text_frame
        tf_b.word_wrap = True
        tf_b.margin_left = tf_b.margin_top = 0
        tf_b.paragraphs[0].text = "Key Business Benefits:"
        tf_b.paragraphs[0].font.size = Pt(10)
        tf_b.paragraphs[0].font.bold = True
        tf_b.paragraphs[0].font.color.rgb = TEXT_DARK

        for pt in d_points:
            p = tf_b.add_paragraph()
            p.text = f"•  {pt}"
            p.font.size = Pt(9)
            p.font.color.rgb = TEXT_MUTED
            p.space_before = Pt(6)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 11: Real-Time Analytics Command Center
    # ═══════════════════════════════════════════════════════════════════════════
    s11 = prs.slides.add_slide(blank_layout)
    set_background(s11, BG_LIGHT)
    add_header(s11, "Executive Visibility & Reporting", "The Analytics Command Center: Continuous Visibility",
               "Real-time visibility into RFI trends, department turnaround bottlenecks, and recurring topic clusters.")

    # 4 Mock KPI Cards from the live dashboard
    add_stat_card(s11, Inches(0.8), Inches(1.8), Inches(2.75), Inches(1.2), "100%", "CTIS SLA Compliance", "Zero missed 10-day validation deadlines", EMERALD)
    add_stat_card(s11, Inches(3.78), Inches(1.8), Inches(2.75), Inches(1.2), "36.4%", "Identified Redundancy", "Over 1/3 of incoming questions are repeats", AMBER)
    add_stat_card(s11, Inches(6.76), Inches(1.8), Inches(2.75), Inches(1.2), "2.5 Days", "Avg. Resolution Time", "Down from 8.5+ days manual turnaround", BLUE_PRIMARY)
    add_stat_card(s11, Inches(9.74), Inches(1.8), Inches(2.75), Inches(1.2), "Top Repeating", "QA (CMC) & Biostats", "Highest frequency of identical inquiries", NAVY_DARK)

    # 2 Big Visual Representation Cards
    vw = Inches(5.65)
    vh = Inches(3.85)
    vtop = Inches(3.2)

    add_content_card(s11, Inches(0.8), vtop, vw, vh, "Recurring Question Clustering (Neo4j Graph)", [
        "Identifies Systemic Documentation Gaps: Clusters repeating RFIs across indications.",
        "Missing Signature Pattern: 12 occurrences across Germany & France for Investigator CVs.",
        "Translation Discrepancies: 8 occurrences in Spanish Patient Information Sheets (PIS).",
        "IMPD Stability Justification: 15 identical questions regarding secondary packaging shelf-life.",
        "Root-Cause Fix: Alerts clinical teams to fix root document templates before submitting next wave."
    ], badge_text="GRAPH INSIGHTS", badge_color=BLUE_PRIMARY)

    add_content_card(s11, Inches(6.88), vtop, vw, vh, "Department Performance & Velocity Tracking", [
        "Biostatistics: 24 RFIs resolved, avg. turnaround 18.2 hours (down from 72h).",
        "Quality Assurance (CMC): 42 RFIs handled, 92% instant response reuse rate.",
        "Regulatory Affairs: 65 RFIs resolved, zero regulatory escalation events.",
        "Affiliate Coordination: Turnaround from country affiliate to HQ slashed by 80%.",
        "Management Reporting: Instant executive export for audit and trial governance meetings."
    ], badge_text="PERFORMANCE TRACKING", badge_color=EMERALD)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 12: Trust, Auditability & GxP Defense (ALCOA+ & OPA)
    # ═══════════════════════════════════════════════════════════════════════════
    s12 = prs.slides.add_slide(blank_layout)
    set_background(s12, BG_LIGHT)
    add_header(s12, "GxP Compliance & Audit Readiness", "Governance by Design: 9-Dimension ALCOA+ & OPA Policy Rules",
               "Built to satisfy the strictest scrutiny from health authorities, FDA/EMA auditors, and internal GxP QA.")

    # Left: The 9 Dimensions of Evidence Integrity
    gw = Inches(5.65)
    gh = Inches(5.0)
    gtop = Inches(1.85)
    add_card(s12, Inches(0.8), gtop, gw, gh, fill_color=CARD_BG)

    tb_g1 = s12.shapes.add_textbox(Inches(1.05), gtop + Inches(0.2), gw - Inches(0.5), gh - Inches(0.4))
    tfg1 = tb_g1.text_frame
    tfg1.word_wrap = True
    tfg1.margin_left = tfg1.margin_top = 0

    p_g1 = tfg1.paragraphs[0]
    p_g1.text = "Evidence Integrity Check (Per-Record ALCOA+)"
    p_g1.font.size = Pt(14)
    p_g1.font.bold = True
    p_g1.font.color.rgb = TEXT_DARK

    alcoa_dims = [
        ("Attributable", "Every record and status change tied to authenticated user ID."),
        ("Legible", "UTF-8 verified plain text; retrievable and immediately renderable."),
        ("Contemporaneous", "Timestamps recorded at moment of state transition."),
        ("Original", "Preserves immutable raw PDF source reference alongside extraction."),
        ("Accurate", "Extracted fields reconciled against source document metadata."),
        ("Complete", "Enforces non-null required fields via policy rule FIELDS-001."),
        ("Consistent", "Zero orphan keys; verified bridge between Postgres and Neo4j."),
        ("Enduring", "Hard deletes prohibited; records are permanent and append-only."),
        ("Available", "Role-based instantaneous retrieval for authorized audit inspection.")
    ]
    for d_name, d_desc in alcoa_dims:
        p = tfg1.add_paragraph()
        p.text = f"✓  {d_name}: "
        p.font.size = Pt(9)
        p.font.bold = True
        p.font.color.rgb = EMERALD
        p.space_before = Pt(3)
        run = p.add_run()
        run.text = d_desc
        run.font.bold = False
        run.font.color.rgb = TEXT_MUTED

    # Right: OPA Declarative Rules & Hash Chain
    add_card(s12, Inches(6.88), gtop, gw, gh, fill_color=CARD_BG)
    tb_g2 = s12.shapes.add_textbox(Inches(7.13), gtop + Inches(0.2), gw - Inches(0.5), gh - Inches(0.4))
    tfg2 = tb_g2.text_frame
    tfg2.word_wrap = True
    tfg2.margin_left = tfg2.margin_top = 0

    p_g2 = tfg2.paragraphs[0]
    p_g2.text = "Declarative Policy Engine & Tamper-Proof Log"
    p_g2.font.size = Pt(14)
    p_g2.font.bold = True
    p_g2.font.color.rgb = TEXT_DARK

    gov_tech = [
        ("Open Policy Agent (OPA / Rego Sidecar)", [
            "Policy as Code: Compliance logic decoupled from application code.",
            "RFI-SLA-001: Flags validation RFIs open > 10 calendar days.",
            "RFI-SLA-002: Flags assessment RFIs open > 12 calendar days.",
            "ACCESS-001: Enforces multi-tenant ownership boundaries."
        ]),
        ("The Inviolable Submission Gate (GATE-001)", [
            "The submitted status is unreachable in the database without an approved_by identity.",
            "Direct API bypass attempts are rejected at the database write layer.",
            "100% human accountability; zero autonomous submission risk."
        ]),
        ("Cryptographic SHA-256 Hash Chain", [
            "Every write computes SHA-256(payload + prev_hash).",
            "Any tampering with database rows invalidates the chain instantly.",
            "Mathematically verifiable audit history for EMA inspections."
        ])
    ]
    for gt_t, gt_points in gov_tech:
        p = tfg2.add_paragraph()
        p.text = f"■  {gt_t}"
        p.font.size = Pt(10.5)
        p.font.bold = True
        p.font.color.rgb = BLUE_PRIMARY
        p.space_before = Pt(7)
        for pt in gt_points:
            pb = tfg2.add_paragraph()
            pb.text = f"  • {pt}"
            pb.font.size = Pt(8.5)
            pb.font.color.rgb = TEXT_MUTED
            pb.space_before = Pt(2)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 13: Enterprise Privacy & In-House LLM Deployment
    # ═══════════════════════════════════════════════════════════════════════════
    s13 = prs.slides.add_slide(blank_layout)
    set_background(s13, BG_LIGHT)
    add_header(s13, "Data Sovereignty & Security", "Enterprise Privacy: Air-Gapped In-House Intelligence",
               "Proprietary clinical trial protocols and confidential drug formulations never leave the enterprise firewall.")

    # 3 Privacy Architecture Pillars
    pw = Inches(3.72)
    ph = Inches(5.0)
    ptop = Inches(1.85)

    add_content_card(s13, Inches(0.8), ptop, pw, ph, "100% On-Premise / VPC LLMs", [
        "Self-Hosted Open-Weights: Deploys Qwen 2.5 7B / Llama 3.1 8B via Ollama or vLLM.",
        "Air-Gapped Operation: Completely isolated inside company private cloud or on-premise servers.",
        "Zero Third-Party Training: Proprietary trial data is never passed to external API vendors.",
        "Quantized Efficiency: GGUF 4-bit quantization runs smoothly on commodity enterprise GPU infrastructure.",
        "Configurable Boundary: Config flag (LLM_MODE) allows switching between local and hosted models without code rewrites."
    ], badge_text="DATA RESIDENCY", badge_color=BLUE_PRIMARY)

    add_content_card(s13, Inches(4.8), ptop, pw, ph, "Deterministic Safety Gateway", [
        "Untrusted Input Boundary: All ingested text from PDFs and queries treated as untrusted content.",
        "OWASP LLM01 Defense: Scans for prompt-injection patterns before text ever reaches model context.",
        "No LLM Self-Policing: Never relies on a generative model to detect prompt manipulation.",
        "Quarantine Routing: Flagged adversarial or corrupt documents automatically routed to human QA queue.",
        "Audited Flagging: Every screening event recorded in the immutable audit log."
    ], badge_text="CYBERSECURITY", badge_color=ROSE)

    add_content_card(s13, Inches(8.8), ptop, pw, ph, "Continuous Fine-Tuning Loop", [
        "Human-in-the-Loop Extraction: Every human edit at the Submission Gate becomes labeled training data.",
        "Extraction Correction Table: Captures corrections to CTR Article tags and MSC mapping automatically.",
        "Periodic LoRA Fine-Tuning: Runs lightweight parameter-efficient fine-tuning on accumulated corrections.",
        "Domain Specialization: Model accuracy continuously adapts to sponsor-specific trial terminology.",
        "Zero Extra Overhead: Reviewers generate training datasets as a natural byproduct of approving drafts."
    ], badge_text="ACTIVE LEARNING", badge_color=EMERALD)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 14: Implementation Roadmap & Phased Enterprise Rollout
    # ═══════════════════════════════════════════════════════════════════════════
    s14 = prs.slides.add_slide(blank_layout)
    set_background(s14, BG_LIGHT)
    add_header(s14, "Implementation & Change Management", "Deployment Roadmap: Rapid 12-Week Value Realization",
               "A non-disruptive, phased integration plan designed for immediate operational wins without system overhaul.")

    phases = [
        ("Phase 1: Weeks 1–4", "Ingestion & Central Repo", [
            "Deploy PostgreSQL + pgvector schema.",
            "Historical RFI PDF ingestion & schema parsing.",
            "Activate pgvector semantic search.",
            "Deliverable: Unified searchable RFI library."
        ], BLUE_PRIMARY),
        ("Phase 2: Weeks 5–8", "Graph & Risk Engine", [
            "Neo4j Knowledge Graph deployment.",
            "Train scikit-learn risk model with SHAP.",
            "Connect hybrid retrieve-then-enrich API.",
            "Deliverable: Predictive pre-submission checks."
        ], AMBER),
        ("Phase 3: Weeks 9–12", "Governance & Rollout", [
            "Deploy OPA policy sidecar & Rego rules.",
            "Enforce Submission Gate (GATE-001).",
            "Launch React role-tailored dashboards.",
            "Deliverable: Full production deployment."
        ], EMERALD),
        ("Phase 4: Ongoing", "Continuous Evolution", [
            "On-premise fine-tuning (LoRA / Ollama).",
            "Expand OPA rules across non-EEA markets.",
            "Portfolio-level Monte Carlo simulation.",
            "Deliverable: Autonomous enterprise scale."
        ], NAVY_DARK),
    ]

    pw_r = Inches(2.76)
    ph_r = Inches(4.8)
    ptop_r = Inches(1.9)
    for i, (p_t, p_st, p_pts, p_c) in enumerate(phases):
        p_l = Inches(0.8) + i * (pw_r + Inches(0.23))
        add_card(s14, p_l, ptop_r, pw_r, ph_r, fill_color=CARD_BG)

        # Header bar
        phb = s14.shapes.add_shape(MSO_SHAPE.RECTANGLE, p_l, ptop_r, pw_r, Inches(0.7))
        phb.fill.solid()
        phb.fill.fore_color.rgb = p_c
        phb.line.fill.background()

        ptxt = s14.shapes.add_textbox(p_l + Inches(0.15), ptop_r + Inches(0.1), pw_r - Inches(0.3), Inches(0.5))
        ptxt.text_frame.margin_left = ptxt.text_frame.margin_top = 0
        ptxt.text_frame.word_wrap = True
        pp = ptxt.text_frame.paragraphs[0]
        pp.text = p_t
        pp.font.size = Pt(11)
        pp.font.bold = True
        pp.font.color.rgb = TEXT_WHITE
        pp2 = ptxt.text_frame.add_paragraph()
        pp2.text = p_st
        pp2.font.size = Pt(9)
        pp2.font.color.rgb = RGBColor(226, 232, 240)

        # Content
        ctb = s14.shapes.add_textbox(p_l + Inches(0.2), ptop_r + Inches(0.85), pw_r - Inches(0.4), ph_r - Inches(1.0))
        ctf = ctb.text_frame
        ctf.word_wrap = True
        ctf.margin_left = ctf.margin_top = 0
        ctf.paragraphs[0].text = "Key Milestones & Deliverables:"
        ctf.paragraphs[0].font.size = Pt(9.5)
        ctf.paragraphs[0].font.bold = True
        ctf.paragraphs[0].font.color.rgb = TEXT_DARK

        for item in p_pts:
            pi = ctf.add_paragraph()
            pi.text = f"•  {item}"
            pi.font.size = Pt(8.5)
            pi.font.color.rgb = TEXT_MUTED
            pi.space_before = Pt(5)

    # ═══════════════════════════════════════════════════════════════════════════
    # SLIDE 15: Executive Conclusion & Call to Action (Dark Theme)
    # ═══════════════════════════════════════════════════════════════════════════
    s15 = prs.slides.add_slide(blank_layout)
    set_background(s15, NAVY_DARK)

    # Accent bar
    bar15 = s15.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.2), Inches(0.8), Inches(0.08))
    bar15.fill.solid()
    bar15.fill.fore_color.rgb = EMERALD
    bar15.line.fill.background()

    tb15 = s15.shapes.add_textbox(Inches(0.8), Inches(1.45), Inches(11.7), Inches(2.2))
    tf15 = tb15.text_frame
    tf15.word_wrap = True
    tf15.margin_left = tf15.margin_top = 0

    p_ct1 = tf15.paragraphs[0]
    p_ct1.text = "EXECUTIVE SUMMARY & NEXT STEPS"
    p_ct1.font.size = Pt(11)
    p_ct1.font.bold = True
    p_ct1.font.color.rgb = EMERALD

    p_ct2 = tf15.add_paragraph()
    p_ct2.text = "The Strategic Choice: Firefighting vs. Institutional Memory"
    p_ct2.font.size = Pt(28)
    p_ct2.font.bold = True
    p_ct2.font.color.rgb = TEXT_WHITE
    p_ct2.space_before = Pt(8)

    p_ct3 = tf15.add_paragraph()
    p_ct3.text = "ClarION transforms a recurring $2.7M compliance liability into an intelligent, permanent competitive advantage."
    p_ct3.font.size = Pt(14)
    p_ct3.font.color.rgb = RGBColor(203, 213, 225)
    p_ct3.space_before = Pt(8)

    # 3 Summary Pillar Cards
    cw15 = Inches(3.72)
    ch15 = Inches(3.2)
    ctop15 = Inches(3.8)

    summary_cards = [
        ("The Hard Business Return", [
            "14,500+ Specialist hours saved annually.",
            "$2.35M In recurring annual operational savings.",
            "4.2-Month Full payback period; 487% 3-year ROI.",
            "Reallocates 8+ FTEs to active pipeline drug launches."
        ], EMERALD),
        ("Uncompromising Governance", [
            "Zero autonomous submissions (Rule GATE-001).",
            "Declarative OPA Rego policies mathematically enforced.",
            "SHA-256 cryptographic audit logs prevent tampering.",
            "Full explainability via SHAP; 100% GxP defensible."
        ], BLUE_ACCENT),
        ("Recommended Immediate Action", [
            "Approve 60-day Pilot with EU Submission Hub.",
            "Connect historical RFI repository across top 3 MSCs.",
            "Validate 70% time compression on live validation RFIs.",
            "Present Pilot outcomes to Executive Committee."
        ], AMBER)
    ]

    for i, (sc_title, sc_bullets, sc_color) in enumerate(summary_cards):
        sc_left = Inches(0.8) + i * (cw15 + Inches(0.28))
        add_card(s15, sc_left, ctop15, cw15, ch15, fill_color=NAVY_SURFACE, border_color=NAVY_LIGHT)

        tb_sc = s15.shapes.add_textbox(sc_left + Inches(0.25), ctop15 + Inches(0.2), cw15 - Inches(0.5), ch15 - Inches(0.4))
        tf_sc = tb_sc.text_frame
        tf_sc.word_wrap = True
        tf_sc.margin_left = tf_sc.margin_top = 0

        p_sct = tf_sc.paragraphs[0]
        p_sct.text = sc_title
        p_sct.font.size = Pt(13)
        p_sct.font.bold = True
        p_sct.font.color.rgb = sc_color

        for b in sc_bullets:
            pb = tf_sc.add_paragraph()
            pb.text = f"•  {b}"
            pb.font.size = Pt(9.5)
            pb.font.color.rgb = RGBColor(226, 232, 240)
            pb.space_before = Pt(6)

    # Save presentation
    output_path = "ClarION_Executive_Showcase.pptx"
    prs.save(output_path)
    print(f"Presentation successfully generated and saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    create_presentation()
