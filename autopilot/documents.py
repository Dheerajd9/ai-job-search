"""Render the tailored resume + cover letter as plain, ATS-safe PDFs (single column,
standard fonts, real text layer). No photo, date of birth or marital status — those
hurt in US/Canada and are optional in India."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=10, leading=13)
NAME = ParagraphStyle("name", parent=BASE, fontName="Helvetica-Bold", fontSize=17, leading=21, alignment=TA_CENTER)
CONTACT = ParagraphStyle("contact", parent=BASE, fontSize=9, alignment=TA_CENTER)
H = ParagraphStyle("h", parent=BASE, fontName="Helvetica-Bold", fontSize=11, spaceBefore=8, spaceAfter=3,
                   textColor="#1f3a5f")
ROLE = ParagraphStyle("role", parent=BASE, fontName="Helvetica-Bold")
SUB = ParagraphStyle("sub", parent=BASE, fontSize=9, textColor="#444444")


def _p(text, style=BASE):
    return Paragraph(escape(str(text or "")), style)


def _pagesize(country: str):
    return A4 if country == "in" else LETTER


def _contact_line(c: dict) -> str:
    parts = [c.get("email"), c.get("phone"), ", ".join(x for x in (c.get("city"), c.get("region")) if x),
             c.get("linkedin"), c.get("github"), c.get("portfolio")]
    return "  |  ".join(p for p in parts if p)


def resume_pdf(path: Path, profile: dict, tailored: dict, country: str) -> Path:
    c = profile["contact"]
    story = [_p(f"{c['first_name']} {c['last_name']}", NAME), _p(_contact_line(c), CONTACT), Spacer(1, 6)]
    if tailored.get("summary"):
        story += [_p("Summary", H), _p(tailored["summary"])]
    story += [_p("Skills", H), _p(", ".join(tailored.get("skills", [])))]
    story.append(_p("Experience", H))
    for exp in profile["experience"]:
        by_id = {b["id"]: b["text"] for b in exp.get("bullets", [])}
        ids = tailored.get("bullets", {}).get(exp["id"]) or list(by_id)[:5]
        items = [ListItem(_p(by_id[i]), leftIndent=10) for i in ids if i in by_id]
        block = [_p(f"{exp['title']} — {exp['company']}", ROLE),
                 _p(f"{exp.get('location', '')}  ·  {exp.get('start', '')} – {exp.get('end', '')}", SUB)]
        if items:
            block.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8))
        story += [KeepTogether(block[:2] + block[2:3]), Spacer(1, 4)]
    if profile.get("education"):
        story.append(_p("Education", H))
        for e in profile["education"]:
            gpa = f" — GPA {e['gpa']}" if e.get("gpa") else ""
            story += [_p(f"{e['degree']}{gpa}", ROLE),
                      _p(f"{e['school']}, {e.get('location', '')}  ·  {e.get('start', '')} – {e.get('end', '')}", SUB)]
    if profile.get("certifications"):
        story.append(_p("Certifications", H))
        for cert in profile["certifications"]:
            story.append(_p(f"{cert['name']} — {cert.get('issuer', '')} ({cert.get('date', '')})"))
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=_pagesize(country), leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            title=f"{c['first_name']} {c['last_name']} Resume", author=f"{c['first_name']} {c['last_name']}")
    doc.build(story)
    return path


def cover_letter_pdf(path: Path, profile: dict, letter: str, company: str, country: str) -> Path | None:
    if not letter:
        return None
    c = profile["contact"]
    story = [_p(f"{c['first_name']} {c['last_name']}", ROLE), _p(_contact_line(c), SUB), Spacer(1, 18),
             _p(f"Dear {company} Hiring Team,"), Spacer(1, 8)]
    for para in [x.strip() for x in letter.split("\n") if x.strip()]:
        story += [_p(para), Spacer(1, 8)]
    story += [Spacer(1, 6), _p("Sincerely,"), _p(f"{c['first_name']} {c['last_name']}")]
    path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(path), pagesize=_pagesize(country), leftMargin=inch, rightMargin=inch,
                      topMargin=inch, bottomMargin=inch).build(story)
    return path
