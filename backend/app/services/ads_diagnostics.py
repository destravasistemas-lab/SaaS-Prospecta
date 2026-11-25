"""
Diagnóstico automático das campanhas.

Recebe os números do período atual e do anterior (por campanha) e devolve
avisos em forma de código + valores; o painel monta o texto no idioma do
usuário. As regras são heurísticas simples e conservadoras: só avisam quando
há volume suficiente para o número significar alguma coisa.
"""
from typing import Any

SEVERITY_ORDER = {"warning": 0, "info": 1, "good": 2}

MIN_RESULTS_TO_COMPARE = 5
CPR_CHANGE = 0.25  # 25%
MIN_SPEND_NO_RESULTS = 50.0
FATIGUE_SHORT = 3.0  # até 14 dias
FATIGUE_LONG = 5.0
MIN_IMPRESSIONS_CTR = 2000
LOW_CTR = 0.8


def diagnose(campaigns: list[dict[str, Any]], perf: dict[str, dict[str, dict]], days: int) -> list[dict[str, Any]]:
    """
    campaigns: [{id, name, effective_status, daily_budget}]
    perf: {campaign_id: {"current": {...insights}, "previous": {...insights}}}
    """
    out: list[dict[str, Any]] = []
    names = {c["id"]: c.get("name") or c["id"] for c in campaigns}

    total_spend = sum(p["current"].get("spend", 0) for p in perf.values())
    total_results = sum(p["current"].get("results", 0) for p in perf.values())
    account_cpr = total_spend / total_results if total_results else 0.0

    def add(code, severity, cid, **values):
        out.append({"code": code, "severity": severity, "campaign_id": cid, "campaign_name": names.get(cid, cid),
                    "values": {k: round(v, 2) if isinstance(v, float) else v for k, v in values.items()}})

    for c in campaigns:
        cid = c["id"]
        p = perf.get(cid)
        cur = (p or {}).get("current") or {}
        prev = (p or {}).get("previous") or {}
        if c.get("effective_status") == "ACTIVE" and not cur.get("impressions"):
            add("not_delivering", "warning", cid)
            continue
        if not p:
            continue

        spend, results = cur.get("spend", 0.0), cur.get("results", 0.0)
        threshold = max(MIN_SPEND_NO_RESULTS, 2 * account_cpr)
        if results == 0 and spend >= threshold:
            add("no_results", "warning", cid, spend=spend)

        cpr, prev_cpr = cur.get("cost_per_result", 0.0), prev.get("cost_per_result", 0.0)
        if results >= MIN_RESULTS_TO_COMPARE and prev.get("results", 0) >= MIN_RESULTS_TO_COMPARE and prev_cpr:
            change = (cpr - prev_cpr) / prev_cpr
            if change >= CPR_CHANGE:
                add("cpr_up", "warning", cid, cpr=cpr, previous=prev_cpr, pct=change * 100)
            elif change <= -CPR_CHANGE:
                add("cpr_down", "good", cid, cpr=cpr, previous=prev_cpr, pct=-change * 100)

        limit = FATIGUE_SHORT if days <= 14 else FATIGUE_LONG
        if cur.get("frequency", 0) >= limit and cur.get("impressions", 0) >= 1000:
            add("fatigue", "warning", cid, frequency=cur["frequency"])

        if cur.get("impressions", 0) >= MIN_IMPRESSIONS_CTR and cur.get("ctr", 0) < LOW_CTR:
            add("low_ctr", "info", cid, ctr=cur.get("ctr", 0.0))

    # Melhor custo só entre campanhas com o mesmo tipo de resultado (lead com lead, clique com clique)
    groups: dict[str, list[tuple[float, str]]] = {}
    for cid, p in perf.items():
        cur = p["current"]
        if cur.get("results", 0) >= MIN_RESULTS_TO_COMPARE and cur.get("cost_per_result"):
            groups.setdefault(cur.get("result_label", ""), []).append((cur["cost_per_result"], cid))
    for label, ranked in groups.items():
        if len(ranked) >= 2:
            best_cpr, best_id = min(ranked)
            add("best", "good", best_id, cpr=best_cpr, label=label)

    out.sort(key=lambda a: SEVERITY_ORDER[a["severity"]])
    return out
