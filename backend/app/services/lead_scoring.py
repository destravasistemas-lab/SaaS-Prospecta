from datetime import datetime, timezone
from app.models.lead import Lead, LeadStatus, LeadSource


def compute_lead_score(lead: Lead) -> dict:
    """Rule-based lead scoring. Returns score (0-100), label and notes."""
    score = 0
    notes: list[str] = []

    if lead.email:
        score += 25
        notes.append("tem e-mail")

    if lead.phone:
        score += 20
        notes.append("tem telefone")

    if lead.name:
        score += 10
        notes.append("identificado")

    source_map = {
        LeadSource.INSTAGRAM_FORM: (20, "formulário Instagram"),
        LeadSource.INSTAGRAM_DM: (15, "DM Instagram"),
        LeadSource.MANUAL: (10, "adicionado manualmente"),
        LeadSource.INSTAGRAM_COMMENT: (5, "comentário Instagram"),
    }
    src_score, src_note = source_map.get(lead.source, (0, ""))
    if src_score:
        score += src_score
        notes.append(src_note)

    # Status bonus
    if lead.status == LeadStatus.QUALIFIED:
        score += 15
        notes.append("qualificado")
    elif lead.status == LeadStatus.CONTACTED:
        score += 5
        notes.append("contactado")
    elif lead.status == LeadStatus.CONVERTED:
        return {"score": 100, "label": "converted", "notes": "lead convertido"}
    elif lead.status == LeadStatus.LOST:
        return {"score": 0, "label": "lost", "notes": "lead perdido"}

    score = min(100, score)

    if score >= 70:
        label = "hot"
    elif score >= 40:
        label = "warm"
    else:
        label = "cold"

    return {
        "score": score,
        "label": label,
        "notes": ", ".join(notes) if notes else "sem dados suficientes",
    }


async def score_lead(lead: Lead) -> Lead:
    result = compute_lead_score(lead)
    lead.score = result["score"]
    lead.score_label = result["label"]
    lead.score_notes = result["notes"]
    lead.last_scored_at = datetime.now(timezone.utc)
    return lead
