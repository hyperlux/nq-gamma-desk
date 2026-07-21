#!/usr/bin/env python3
"""Export a FlashAlpha NQ report directory (raw/*.json) into site data/latest.json.

Usage:
  python3 export_latest.py /path/to/nq_report_YYYYMMDD_HHMMSS [/path/to/site]
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys
from zoneinfo import ZoneInfo


def load(raw: pathlib.Path, name: str):
    p = raw / f"{name}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def fnum(x, default=None):
    if x is None:
        return default
    try:
        return float(x)
    except Exception:
        return default


def fmt_gex(x):
    if x is None:
        return None
    x = float(x)
    sign = "+" if x > 0 else ("-" if x < 0 else "")
    ax = abs(x)
    if ax >= 1e9:
        return f"{sign}{ax/1e9:.2f}B"
    if ax >= 1e6:
        return f"{sign}{ax/1e6:.2f}M"
    if ax >= 1e3:
        return f"{sign}{ax/1e3:.1f}K"
    return f"{sign}{ax:.0f}"


def top_strikes(strikes, key="net_gex", n=8, reverse=True, near_spot=None, band=1500):
    if not strikes:
        return []
    rows = strikes
    if near_spot is not None:
        rows = [s for s in strikes if abs(fnum(s.get("strike"), 0) - near_spot) <= band]
        if not rows:
            rows = strikes
    ordered = sorted(rows, key=lambda s: fnum(s.get(key), 0), reverse=reverse)
    out = []
    for s in ordered[:n]:
        out.append(
            {
                "strike": fnum(s.get("strike")),
                "net_gex": fnum(s.get("net_gex")),
                "net_gex_display": fmt_gex(s.get("net_gex")),
                "call_gex": fnum(s.get("call_gex")),
                "put_gex": fnum(s.get("put_gex")),
                "call_oi": s.get("call_oi"),
                "put_oi": s.get("put_oi"),
                "call_volume": s.get("call_volume"),
                "put_volume": s.get("put_volume"),
                "net_dex": fnum(s.get("net_dex")),
                "net_vex": fnum(s.get("net_vex")),
                "dag": fnum(s.get("dag")),
            }
        )
    return out


def corridor_gex(strikes, spot, band=1000):
    if not strikes or spot is None:
        return None
    total = 0.0
    n = 0
    for s in strikes:
        k = fnum(s.get("strike"))
        if k is None:
            continue
        if abs(k - spot) <= band:
            total += fnum(s.get("net_gex"), 0) or 0
            n += 1
    return {"band": band, "net_gex": total, "net_gex_display": fmt_gex(total), "strike_count": n}


def build_gex_profile(strikes, spot, lo=None, hi=None, step_merge=25):
    """Compact profile for spark/bar chart around spot."""
    if not strikes or spot is None:
        return []
    lo = lo if lo is not None else spot - 1200
    hi = hi if hi is not None else spot + 1200
    rows = []
    for s in strikes:
        k = fnum(s.get("strike"))
        if k is None or k < lo or k > hi:
            continue
        g = fnum(s.get("net_gex"), 0) or 0
        if abs(g) < 1:  # skip empty
            continue
        rows.append(
            {
                "strike": k,
                "net_gex": g,
                "net_gex_display": fmt_gex(g),
                "call_oi": s.get("call_oi") or 0,
                "put_oi": s.get("put_oi") or 0,
            }
        )
    rows.sort(key=lambda x: x["strike"])
    # keep top-magnitude + evenly spaced sample if too dense
    if len(rows) > 48:
        by_mag = sorted(rows, key=lambda x: abs(x["net_gex"]), reverse=True)[:36]
        keep = {r["strike"] for r in by_mag}
        # always keep round hundreds near spot
        for r in rows:
            if abs(r["strike"] - spot) <= 400 and r["strike"] % 100 == 0:
                keep.add(r["strike"])
        rows = [r for r in rows if r["strike"] in keep]
        rows.sort(key=lambda x: x["strike"])
    return rows


def main():
    if len(sys.argv) < 2:
        print("Usage: export_latest.py REPORT_DIR [SITE_DIR]", file=sys.stderr)
        sys.exit(2)
    report = pathlib.Path(sys.argv[1]).resolve()
    site = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else report.parent / "nq-gamma-desk"
    raw = report / "raw"
    if not raw.is_dir():
        print(f"No raw/ in {report}", file=sys.stderr)
        sys.exit(1)

    account = load(raw, "account") or {}
    levels = load(raw, "levels") or {}
    summary = load(raw, "summary") or {}
    zdte = load(raw, "zero_dte") or {}
    narrative = load(raw, "narrative") or {}
    maxpain = load(raw, "maxpain") or {}
    em = load(raw, "expected_move") or {}
    flow_sum = load(raw, "flow_summary") or {}
    flow_pin = load(raw, "flow_pin") or {}
    flow_lv = load(raw, "flow_levels") or {}
    flow_dealer = load(raw, "flow_dealer_risk") or {}
    gex = load(raw, "gex") or {}
    sheet = load(raw, "sheet") or {}
    term = load(raw, "term_structure") or {}
    oi_diff = load(raw, "oi_diff") or {}
    vol = load(raw, "volatility") or {}
    skew = load(raw, "skew_term") or {}
    liq = load(raw, "liquidity") or {}
    qqq_zdte = load(raw, "qqq_zero_dte") or {}
    qqq_lv = load(raw, "qqq_levels") or {}
    qqq_sum = load(raw, "qqq_summary") or {}
    qqq_narr = load(raw, "qqq_narrative") or {}
    qqq_mp = load(raw, "qqq_maxpain") or {}
    qqq_flow = load(raw, "qqq_flow_summary") or {}
    qqq_pin = load(raw, "qqq_flow_pin") or {}
    ndx_lv = load(raw, "ndx_levels") or {}
    ndx_sum = load(raw, "ndx_summary") or {}
    vix = load(raw, "vix") or {}

    L = levels.get("levels") or {}
    spot = fnum(levels.get("underlying_price") or summary.get("underlying_price") or gex.get("underlying_price"))
    flip = fnum(L.get("gamma_flip") or summary.get("gamma_flip") or gex.get("gamma_flip"))
    call_wall = fnum(L.get("call_wall"))
    put_wall = fnum(L.get("put_wall"))
    max_pos = fnum(L.get("max_positive_gamma"))
    max_neg = fnum(L.get("max_negative_gamma"))
    hi_oi = fnum(L.get("highest_oi_strike"))
    magnet_lv = fnum(L.get("zero_dte_magnet"))

    vs_flip = "n/a"
    dist_flip = None
    if spot is not None and flip is not None:
        dist_flip = spot - flip
        vs_flip = "above" if spot > flip else ("below" if spot < flip else "at")

    exposures = summary.get("exposures") or {}
    net_gex = fnum(exposures.get("net_gex") if exposures else gex.get("net_gex"))
    net_dex = fnum(exposures.get("net_dex"))
    net_vex = fnum(exposures.get("net_vex"))
    net_chex = fnum(exposures.get("net_chex"))
    regime = summary.get("regime") or gex.get("net_gex_label") or "unknown"
    interp = summary.get("interpretation") or {}
    hedge = summary.get("hedging_estimate") or {}

    if vs_flip == "below":
        local_regime = "negative_gamma"
    elif vs_flip == "above":
        local_regime = "positive_gamma"
    else:
        local_regime = str(regime)

    if vs_flip == "below" and dist_flip is not None and abs(dist_flip) < 50:
        bias = "FLIP-ZONE / NEGATIVE GAMMA"
        bias_detail = (
            "Spot is hugging the gamma flip from below — two-way hinge risk. "
            "Acceptance away from flip can trend; chop fades need tight invalidation."
        )
        bias_tone = "warn"
    elif vs_flip == "below":
        bias = "BELOW FLIP / NEGATIVE GAMMA"
        bias_detail = "Dealers short gamma below flip — dips/rallies can amplify. Prefer momentum confirmation over pure mean-revert."
        bias_tone = "bear"
    elif vs_flip == "above" and dist_flip is not None and abs(dist_flip) < 50:
        bias = "FLIP-ZONE / POSITIVE GAMMA"
        bias_detail = "Just above flip — local long-gamma cushion forming, but hinge still active until accepted higher."
        bias_tone = "warn"
    elif vs_flip == "above":
        bias = "ABOVE FLIP / POSITIVE GAMMA"
        bias_detail = "Long-gamma cushion — mean-revert bias into walls; fade extremes with structure."
        bias_tone = "bull"
    else:
        bias = "UNKNOWN"
        bias_detail = "Insufficient flip/spot context."
        bias_tone = "neutral"

    zd_exp = zdte.get("exposures") or {}
    zd_em = zdte.get("expected_move") or {}
    zd_pin = zdte.get("pin_risk") or {}
    pin_score = fnum(zd_pin.get("pin_score") or flow_pin.get("live_pin_risk"), 0) or 0
    magnet = fnum(zd_pin.get("magnet_strike") or magnet_lv)
    zd_mp = fnum(zd_pin.get("max_pain"))
    em_1sd = fnum(zd_em.get("implied_1sd_dollars"))
    em_up = fnum(zd_em.get("upper_bound"))
    em_dn = fnum(zd_em.get("lower_bound"))
    em_pct = fnum(zd_em.get("implied_1sd_pct"))
    atm_iv_zd = fnum(zd_em.get("atm_iv"))

    nq_0dte_empty = bool(zdte.get("no_zero_dte"))
    if not nq_0dte_empty:
        if (
            fnum(zd_exp.get("net_gex"), 0) == 0
            and pin_score <= 2
            and magnet
            and spot
            and abs(magnet - spot) / spot > 0.15
        ):
            nq_0dte_empty = True

    pin_quality = (
        "hard"
        if pin_score >= 60
        else ("moderate" if pin_score >= 40 else ("weak" if pin_score >= 20 else "none"))
    )

    mp = fnum(maxpain.get("max_pain_strike") or maxpain.get("max_pain"))
    mp_dist = maxpain.get("distance") or {}
    mp_sig = maxpain.get("signal")
    mp_exp = maxpain.get("expiration")
    mp_pcr = fnum(maxpain.get("put_call_oi_ratio"))
    mp_align = maxpain.get("dealer_alignment") or {}
    mp_pin_prob = fnum(maxpain.get("pin_probability"))
    mp_by_exp = []
    for row in (maxpain.get("max_pain_by_expiration") or [])[:12]:
        if fnum(row.get("total_oi"), 0) in (0, None) and fnum(row.get("dte"), 99) > 60:
            continue
        mp_by_exp.append(
            {
                "expiration": row.get("expiration"),
                "dte": row.get("dte"),
                "max_pain_strike": fnum(row.get("max_pain_strike")),
                "total_oi": row.get("total_oi"),
            }
        )
    # keep nearest with OI
    mp_by_exp = [r for r in (maxpain.get("max_pain_by_expiration") or []) if (r.get("total_oi") or 0) > 0][:10]
    mp_by_exp = [
        {
            "expiration": r.get("expiration"),
            "dte": r.get("dte"),
            "max_pain_strike": fnum(r.get("max_pain_strike")),
            "total_oi": r.get("total_oi"),
        }
        for r in mp_by_exp
    ]

    narr = narrative.get("narrative") if isinstance(narrative.get("narrative"), dict) else {}
    if not narr and isinstance(narrative, dict) and "regime" in narrative:
        narr = narrative

    # GEX strike map
    gex_strikes = gex.get("strikes") or sheet.get("strikes") or []
    peaks_raw = sheet.get("peaks") or []
    peaks = sorted(peaks_raw, key=lambda p: abs(fnum(p.get("net_gex"), 0) or 0), reverse=True)[:14]
    peaks_out = []
    for p in peaks:
        pk = fnum(p.get("strike"))
        peaks_out.append(
            {
                "strike": pk,
                "net_gex": fnum(p.get("net_gex")),
                "net_gex_display": fmt_gex(p.get("net_gex")),
                "strength": fnum(p.get("strength")),
                "side": p.get("side"),
                "dist": None if spot is None or pk is None else pk - spot,
            }
        )

    pos_near = top_strikes(gex_strikes, reverse=True, n=8, near_spot=spot, band=1500)
    neg_near = top_strikes(gex_strikes, reverse=False, n=8, near_spot=spot, band=1500)
    pos_global = top_strikes(gex_strikes, reverse=True, n=6, near_spot=None)
    neg_global = top_strikes(gex_strikes, reverse=False, n=6, near_spot=None)
    local_corr = corridor_gex(gex_strikes, spot, 1000)
    local_corr_wide = corridor_gex(gex_strikes, spot, 500)
    gex_profile = build_gex_profile(gex_strikes, spot)

    # add nearest large nodes into ladder
    extra_ladder_nodes = []
    for s in neg_near[:4]:
        if s["strike"] and spot and abs(s["strike"] - spot) > 15:
            extra_ladder_nodes.append((s["strike"], f"−GEX {int(s['strike'])}", "neg_gex", abs(s.get("net_gex") or 0) > 4e7, s.get("net_gex_display")))
    for s in pos_near[:4]:
        if s["strike"] and spot and abs(s["strike"] - spot) > 15:
            extra_ladder_nodes.append((s["strike"], f"+GEX {int(s['strike'])}", "pos_gex", abs(s.get("net_gex") or 0) > 3e7, s.get("net_gex_display")))

    # OI diff
    oi_top = []
    for row in (oi_diff.get("top_oi_changes") or [])[:12]:
        oi_top.append(
            {
                "strike": fnum(row.get("strike")),
                "type": row.get("type"),
                "expiry": row.get("expiry"),
                "today_oi": row.get("today_oi"),
                "prior_oi": row.get("prior_oi"),
                "oi_change": row.get("oi_change"),
            }
        )

    # Term structure
    by_bucket = []
    for b in term.get("by_dte_bucket") or []:
        by_bucket.append(
            {
                "bucket": b.get("bucket"),
                "dte_range": b.get("dte_range"),
                "net_gex": fnum(b.get("net_gex")),
                "net_gex_display": fmt_gex(b.get("net_gex")),
                "net_dex": fnum(b.get("net_dex")),
                "net_dex_display": fmt_gex(b.get("net_dex")),
                "net_vex": fnum(b.get("net_vex")),
                "net_vex_display": fmt_gex(b.get("net_vex")),
                "net_chex": fnum(b.get("net_chex")),
                "contract_count": b.get("contract_count"),
            }
        )
    by_expiry = []
    for e in (term.get("by_expiry") or [])[:14]:
        by_expiry.append(
            {
                "expiration": e.get("expiration"),
                "dte": e.get("dte"),
                "is_opex": e.get("is_opex"),
                "net_gex": fnum(e.get("net_gex")),
                "net_gex_display": fmt_gex(e.get("net_gex")),
                "pct_of_chain_gex": fnum(e.get("pct_of_chain_gex")),
                "net_dex": fnum(e.get("net_dex")),
                "net_vex": fnum(e.get("net_vex")),
            }
        )

    # Vol
    rv = vol.get("realized_vol") or {}
    vrp = vol.get("iv_rv_spreads") or {}
    vol_term = vol.get("term_structure") or {}
    skew_rows = []
    for s in (vol.get("skew_profiles") or skew.get("expiries") or [])[:10]:
        skew_rows.append(
            {
                "expiry": s.get("expiry") or s.get("expiration"),
                "dte": s.get("days_to_expiry") or s.get("dte"),
                "atm_iv": fnum(s.get("atm_iv")),
                "put_25d_iv": fnum(s.get("put_25d_iv")),
                "call_25d_iv": fnum(s.get("call_25d_iv")),
                "put_10d_iv": fnum(s.get("put_10d_iv")),
                "call_10d_iv": fnum(s.get("call_10d_iv")),
                "skew_25d": fnum(s.get("skew_25d")),
                "smile_ratio": fnum(s.get("smile_ratio")),
                "tail_convexity": fnum(s.get("tail_convexity")),
                "risk_reversal_25d": fnum(s.get("risk_reversal_25d")),
            }
        )
    pc_prof = vol.get("put_call_profile") or {}
    pc_by_exp = []
    for r in (pc_prof.get("by_expiry") or [])[:12]:
        pc_by_exp.append(
            {
                "expiry": r.get("expiry"),
                "call_oi": r.get("call_oi"),
                "put_oi": r.get("put_oi"),
                "pc_ratio_oi": fnum(r.get("pc_ratio_oi")),
                "call_volume": r.get("call_volume"),
                "put_volume": r.get("put_volume"),
                "pc_ratio_volume": fnum(r.get("pc_ratio_volume")),
            }
        )
    hedge_scen = []
    for h in vol.get("hedging_scenarios") or []:
        hedge_scen.append(
            {
                "move_pct": h.get("move_pct"),
                "dealer_shares": h.get("dealer_shares"),
                "direction": h.get("direction"),
                "notional_usd": h.get("notional_usd"),
                "notional_display": fmt_gex(h.get("notional_usd")),
            }
        )

    # QQQ / NDX
    QL = (qqq_lv or {}).get("levels") or {}
    qz_pin = (qqq_zdte or {}).get("pin_risk") or {}
    qz_em = (qqq_zdte or {}).get("expected_move") or {}
    qqq_spot = fnum((qqq_lv or {}).get("underlying_price") or (qqq_sum or {}).get("underlying_price"))
    qqq_flip = fnum(QL.get("gamma_flip") or (qqq_sum or {}).get("gamma_flip"))
    qqq_vs = "n/a"
    if qqq_spot is not None and qqq_flip is not None:
        qqq_vs = "above" if qqq_spot > qqq_flip else ("below" if qqq_spot < qqq_flip else "at")
    qn = qqq_narr.get("narrative") if isinstance((qqq_narr or {}).get("narrative"), dict) else {}
    if not isinstance(qn, dict):
        qn = {}
    NL = (ndx_lv or {}).get("levels") or {}
    ndx_spot = fnum((ndx_lv or {}).get("underlying_price") or (ndx_sum or {}).get("underlying_price"))
    ndx_flip = fnum(NL.get("gamma_flip") or (ndx_sum or {}).get("gamma_flip"))
    ndx_vs = "n/a"
    if ndx_spot is not None and ndx_flip is not None:
        ndx_vs = "above" if ndx_spot > ndx_flip else ("below" if ndx_spot < ndx_flip else "at")

    ems = em.get("expected_moves") or []
    em_term = []
    for e in ems[:12]:
        em_term.append(
            {
                "expiry": e.get("expiry"),
                "dte": e.get("daysToExpiry"),
                "atm_iv": fnum(e.get("atmIv")),
                "move": fnum(e.get("expectedMove")),
                "move_pct": fnum(e.get("expectedMovePct")),
                "lower": fnum(e.get("lowerBound")),
                "upper": fnum(e.get("upperBound")),
            }
        )

    # Ladder
    ladder = []

    def add_lvl(price, label, kind, emphasis=False, note=None):
        if price is None:
            return
        ladder.append(
            {
                "price": float(price),
                "label": label,
                "kind": kind,
                "emphasis": bool(emphasis),
                "note": note,
                "dist": None if spot is None else float(price) - float(spot),
            }
        )

    add_lvl(call_wall, "Call wall", "call_wall", True, "Remote resistance / dealer call concentration")
    add_lvl(max_pos, "Max +GEX", "pos_gex", False, "Chain max positive gamma node")
    add_lvl(em_up, "0DTE +1σ", "em_up", True, "Same-day upper expected move")
    add_lvl(magnet, "0DTE magnet", "magnet", pin_quality in ("hard", "moderate"), f"Pin score {pin_score:.0f}/100 — {pin_quality}")
    add_lvl(mp, "Max pain", "pain", True, f"Expiry {mp_exp}" if mp_exp else None)
    add_lvl(flip, "Gamma flip", "flip", True, "Regime line — primary hinge")
    add_lvl(spot, "Spot", "spot", True, "Last underlying at pull")
    add_lvl(zd_mp, "0DTE max pain", "pain", False, "Same-day pain")
    add_lvl(em_dn, "0DTE −1σ", "em_dn", True, "Same-day lower expected move")
    add_lvl(max_neg, "Max −GEX", "neg_gex", False, "Chain max negative gamma node")
    add_lvl(put_wall, "Put wall", "put_wall", True, "Remote support / dealer put concentration")
    add_lvl(hi_oi, "Highest OI", "oi", False, "Peak open interest strike")
    for price, label, kind, emph, note in extra_ladder_nodes:
        add_lvl(price, label, kind, emph, note)

    ladder.sort(key=lambda x: -x["price"])
    deduped = []
    for item in ladder:
        if deduped and abs(deduped[-1]["price"] - item["price"]) < 0.75:
            if item["kind"] != deduped[-1]["kind"]:
                deduped[-1]["label"] = f"{deduped[-1]['label']} · {item['label']}"
                deduped[-1]["emphasis"] = deduped[-1]["emphasis"] or item["emphasis"]
            continue
        deduped.append(item)
    ladder = deduped

    # Scenarios
    scenarios = []
    if spot is not None and flip is not None:
        t1 = round(mp) if mp else None
        t2 = round(em_up) if em_up else None
        t3 = round(magnet) if magnet and pin_quality != "none" else None
        # nearest +GEX above
        above_pos = [s for s in pos_near if s["strike"] and s["strike"] > spot]
        if above_pos:
            t_pos = round(above_pos[0]["strike"])
        else:
            t_pos = None
        below_neg = [s for s in neg_near if s["strike"] and s["strike"] < spot]
        t_neg = round(below_neg[0]["strike"]) if below_neg else (round(max_neg) if max_neg else None)

        scenarios.append(
            {
                "id": "A",
                "name": "Flip reclaim & hold",
                "side": "long",
                "tone": "bull",
                "trigger": f"15–30m acceptance above ~{flip+25:.0f}–{flip+55:.0f} after clearing flip {flip:.0f}",
                "entry_zone": [round(flip + 15), round(flip + 55)],
                "targets": [x for x in [t1, t_pos, t2, t3] if x is not None],
                "invalidation": round(min(spot, flip) - 45),
                "invalidation_note": f"Back below ~{min(spot, flip)-35:.0f} with momentum / failed hold",
                "why": (
                    f"Leaving the hinge reduces forced dealer sell-the-rip. Local corridor GEX "
                    f"{(local_corr or {}).get('net_gex_display', 'n/a')} (±1k). Pain/magnet sit {('overhead' if (mp or 0) > spot else 'nearby')}."
                ),
                "management": "Scale 1/2 into first +GEX/pain; trail under higher lows if flow wakes bullish.",
            }
        )
        scenarios.append(
            {
                "id": "B",
                "name": "Flip reject / downside expansion",
                "side": "short",
                "tone": "bear",
                "trigger": f"Failure at flip and acceptance below ~{spot-40:.0f}–{spot-80:.0f}",
                "entry_zone": [round(spot - 90), round(spot - 35)],
                "targets": [x for x in [round(em_dn) if em_dn else None, t_neg, round(put_wall) if put_wall else None] if x is not None],
                "invalidation": round(flip + 55) if flip else None,
                "invalidation_note": f"Swift reclaim >{flip+50:.0f} and hold",
                "why": (
                    f"Chain net GEX {fmt_gex(net_gex)} with short-gamma local regime. "
                    f"Nearest fuel nodes: {', '.join(str(int(s['strike'])) for s in neg_near[:3] if s.get('strike'))}."
                ),
                "management": "Do not average into acceleration; cover partials into −GEX shelves (28.8k/28.5k/28k).",
            }
        )
        scenarios.append(
            {
                "id": "C",
                "name": "Hinge chop / mean-test",
                "side": "range",
                "tone": "neutral",
                "trigger": "Price holds inside 0DTE 1σ with repeated tests of flip / max pain; flow still quiet",
                "entry_zone": [round(em_dn) if em_dn else None, round(em_up) if em_up else None],
                "targets": [x for x in [round(flip) if flip else None, round(mp) if mp else None] if x is not None],
                "invalidation": None,
                "invalidation_note": "Impulsive break beyond 1σ with rising live flow shift or corridor GEX flip",
                "why": (
                    f"Pin quality is {pin_quality} ({pin_score:.0f}/100). "
                    f"NQ flow={flow_sum.get('flow_direction') or 'n/a'}; prefer structure over magnet fades."
                ),
                "management": "Fade edges only with tight stops; stand down if VIX pops while GEX stays negative.",
            }
        )
        # Acceleration pocket scenario if strong neg node between spot and lower
        if below_neg:
            scenarios.append(
                {
                    "id": "D",
                    "name": "Neg-GEX air pocket ride",
                    "side": "short",
                    "tone": "bear",
                    "trigger": f"Break/hold under {below_neg[0]['strike']:.0f} (−GEX shelf) with expanding range",
                    "entry_zone": [round(below_neg[0]["strike"] - 40), round(below_neg[0]["strike"] - 5)],
                    "targets": [round(s["strike"]) for s in below_neg[1:4] if s.get("strike")],
                    "invalidation": round(below_neg[0]["strike"] + 60),
                    "invalidation_note": f"Reclaim of {below_neg[0]['strike']:.0f} shelf",
                    "why": "Negative gamma nodes can act as fuel on the way down until a larger put wall absorbs.",
                    "management": "Intraday only; size down — short gamma days gap through levels.",
                }
            )

    for s in scenarios:
        s["targets"] = [t for t in s["targets"] if t is not None]
        if s.get("entry_zone") and any(x is None for x in s["entry_zone"]):
            s["entry_zone"] = [x for x in s["entry_zone"] if x is not None]

    # Trading narrative bullets (human scalp brief)
    narrative_bullets = []
    narrative_bullets.append(
        f"NQ {spot:.2f} is {vs_flip} gamma flip {flip:.1f} by {abs(dist_flip):.1f} pts — local regime **{local_regime}** (chain label {regime})."
        if spot and flip and dist_flip is not None
        else f"Regime {regime}."
    )
    narrative_bullets.append(
        f"Chain net GEX {fmt_gex(net_gex)}; local ±500 corridor {fmt_gex((local_corr_wide or {}).get('net_gex'))}, ±1000 {fmt_gex((local_corr or {}).get('net_gex'))}."
    )
    if by_bucket:
        near = next((b for b in by_bucket if b.get("bucket") == "0-7d"), None)
        mid = next((b for b in by_bucket if b.get("bucket") == "8-30d"), None)
        if near and mid:
            narrative_bullets.append(
                f"Term split: 0–7d GEX {near['net_gex_display']} vs 8–30d {mid['net_gex_display']} — "
                f"{'front supportive / belly short' if (near.get('net_gex') or 0) > 0 > (mid.get('net_gex') or 0) else 'mixed term structure'}."
            )
    narrative_bullets.append(
        f"0DTE pin {pin_score:.0f}/100 ({pin_quality}); magnet {magnet:.0f} · 1σ ±{em_1sd:.0f} → {em_dn:.0f}–{em_up:.0f}."
        if magnet and em_1sd and em_dn and em_up
        else f"0DTE pin {pin_score:.0f}/100 ({pin_quality})."
    )
    if nq_0dte_empty:
        narrative_bullets.append("NQ same-day futures options book looks empty/non-actionable — lean on QQQ cash proxy for pin.")
    narrative_bullets.append(
        f"Flow: NQ `{flow_sum.get('flow_direction') or 'n/a'}` ({flow_sum.get('contracts_with_flow') or 0}/{flow_sum.get('contracts_total') or 0} contracts). Settled GEX is boss until live flow wakes."
    )
    if oi_top:
        puts = [x for x in oi_top if x.get("type") == "P"][:3]
        if puts:
            narrative_bullets.append(
                "OI build: "
                + ", ".join(f"{int(p['strike'])}P {p.get('oi_change'):+d} ({p.get('expiry')})" for p in puts if p.get("strike") is not None)
                + f" · call ΔOI {oi_diff.get('total_call_oi_change')} / put ΔOI {oi_diff.get('total_put_oi_change')}."
            )
    if qqq_spot and qqq_flip:
        narrative_bullets.append(
            f"QQQ {qqq_spot:.2f} {qqq_vs} flip {qqq_flip:.2f} · regime {(qqq_sum or {}).get('regime')} · "
            f"0DTE GEX share {fnum(((qqq_sum or {}).get('zero_dte') or {}).get('pct_of_total_gex'))}%."
        )
    if ndx_spot and ndx_flip:
        narrative_bullets.append(
            f"NDX {ndx_spot:.1f} {ndx_vs} flip {ndx_flip:.1f} · regime {(ndx_sum or {}).get('regime')} "
            f"(cross-check — NDX can disagree with NQ/QQQ)."
        )
    if vix:
        narrative_bullets.append(
            f"VIX {fnum(vix.get('vix')):.1f} vs SPX RV20 {fnum(vix.get('spx_rv_20d')):.1f} ({vix.get('state')}) — {vix.get('interpretation')}"
        )
    if vol:
        narrative_bullets.append(
            f"NQ ATM IV {fnum(vol.get('atm_iv')):.1f} · RV20 {fnum(rv.get('rv_20d')):.1f} · VRP {vrp.get('assessment')} "
            f"(VRP20 {fnum(vrp.get('vrp_20d'))}) · IV term {vol_term.get('state')}."
        )
    if mp_align:
        narrative_bullets.append(mp_align.get("description") or f"Max pain {mp:.0f} signal {mp_sig}.")
    if interp:
        narrative_bullets.append(f"Dealer interp — γ: {interp.get('gamma')} | ν: {interp.get('vanna')} | χ: {interp.get('charm')}")

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_et = datetime.datetime.now(ZoneInfo("America/New_York"))
    reqs = None
    flog = report / "fetch_log.tsv"
    if flog.exists():
        reqs = sum(1 for line in flog.read_text().splitlines() if line.strip())

    session_note = "cash-hours proxy / futures book"
    if zdte.get("market_open") is False:
        session_note = "FlashAlpha flags market_open=false on NQ 0DTE flow series — treat live flow as unsettled/quiet"
    elif zdte.get("market_open") is True:
        session_note = "0DTE session open"

    out = {
        "meta": {
            "symbol": "NQ=F",
            "title": "NQ Gamma Desk",
            "generated_at_utc": now_utc.isoformat(),
            "generated_at_et": now_et.strftime("%Y-%m-%d %H:%M %Z"),
            "as_of": levels.get("as_of") or summary.get("as_of") or gex.get("as_of"),
            "source": "FlashAlpha",
            "report_dir": str(report),
            "plan": account.get("plan"),
            "usage_today": account.get("usage_today"),
            "remaining": account.get("remaining"),
            "requests_this_pull": reqs,
            "depth": "full",
            "session_note": session_note,
            "disclaimer": "Not investment advice. Dealer-positioning model from FlashAlpha; NQ options-on-futures via Black-76. For discretionary scalping context only.",
        },
        "spot": {
            "price": spot,
            "regime": regime,
            "local_regime": local_regime,
            "gamma_flip": flip,
            "spot_vs_flip": vs_flip,
            "distance_to_flip": dist_flip,
            "net_gex": net_gex,
            "net_gex_display": fmt_gex(net_gex),
            "net_dex": net_dex,
            "net_dex_display": fmt_gex(net_dex),
            "net_vex": net_vex,
            "net_vex_display": fmt_gex(net_vex),
            "net_chex": net_chex,
            "net_chex_display": fmt_gex(net_chex),
            "bias": bias,
            "bias_detail": bias_detail,
            "bias_tone": bias_tone,
            "local_corridor_500": local_corr_wide,
            "local_corridor_1000": local_corr,
        },
        "levels": {
            "call_wall": call_wall,
            "put_wall": put_wall,
            "gamma_flip": flip,
            "max_positive_gamma": max_pos,
            "max_negative_gamma": max_neg,
            "highest_oi_strike": hi_oi,
            "zero_dte_magnet": magnet_lv,
            "max_pain": mp,
            "max_pain_expiration": mp_exp,
            "max_pain_signal": mp_sig,
            "max_pain_distance": mp_dist,
            "put_call_oi_ratio": mp_pcr,
            "pin_probability": mp_pin_prob,
            "dealer_alignment": mp_align,
            "lis": sheet.get("lis"),
            "is_opex": sheet.get("is_opex"),
            "is_triple_witching": sheet.get("is_triple_witching"),
        },
        "ladder": ladder,
        "gex_map": {
            "peaks": peaks_out,
            "positive_near": pos_near,
            "negative_near": neg_near,
            "positive_global": pos_global,
            "negative_global": neg_global,
            "profile": gex_profile,
            "totals": sheet.get("totals") or {
                "net_gex": net_gex,
                "net_dex": net_dex,
                "net_vex": net_vex,
                "net_chex": net_chex,
            },
        },
        "zero_dte": {
            "expiration": zdte.get("expiration"),
            "market_open": zdte.get("market_open"),
            "time_to_close_hours": zdte.get("time_to_close_hours"),
            "time_to_close_pct": zdte.get("time_to_close_pct"),
            "regime": zdte.get("regime"),
            "net_gex": fnum(zd_exp.get("net_gex")),
            "net_gex_display": fmt_gex(zd_exp.get("net_gex")),
            "pct_of_total_gex": fnum(zd_exp.get("pct_of_total_gex") or (summary.get("zero_dte") or {}).get("pct_of_total_gex")),
            "pin_score": pin_score,
            "pin_quality": pin_quality,
            "magnet": magnet,
            "max_pain": zd_mp,
            "em_1sd": em_1sd,
            "em_1sd_pct": em_pct,
            "em_upper": em_up,
            "em_lower": em_dn,
            "atm_iv": atm_iv_zd,
            "straddle": fnum(zd_em.get("straddle_price")),
            "description": zd_pin.get("description"),
            "components": zd_pin.get("components"),
            "empty_book": nq_0dte_empty,
            "note": (
                "NQ 0DTE book empty/non-actionable — prefer QQQ proxy for cash pin."
                if nq_0dte_empty
                else (
                    f"Pin is {pin_quality}; treat magnet as soft target."
                    if pin_quality in ("weak", "none")
                    else f"Pin quality {pin_quality}."
                )
            ),
        },
        "flow": {
            "direction": flow_sum.get("flow_direction"),
            "live_gex": fnum(flow_sum.get("live_gex")),
            "live_gex_display": fmt_gex(flow_sum.get("live_gex")),
            "flow_gex_pct_shift": fnum(flow_sum.get("flow_gex_pct_shift")),
            "contracts_with_flow": flow_sum.get("contracts_with_flow"),
            "contracts_total": flow_sum.get("contracts_total"),
            "intraday_oi_delta": flow_sum.get("intraday_oi_delta"),
            "live_gamma_flip": fnum(flow_lv.get("live_gamma_flip")),
            "live_call_wall": fnum(flow_lv.get("live_call_wall")),
            "live_put_wall": fnum(flow_lv.get("live_put_wall")),
            "live_max_pain": fnum(flow_lv.get("live_max_pain")),
            "live_pin_risk": fnum(flow_pin.get("live_pin_risk")),
            "magnet_strike": fnum(flow_pin.get("magnet_strike")),
            "dealer_risk": {
                "description": flow_dealer.get("description"),
                "flow_direction": flow_dealer.get("flow_direction"),
                "settled_net_gex": fnum(flow_dealer.get("settled_net_gex")),
                "live_net_gex": fnum(flow_dealer.get("live_net_gex")),
                "flow_gex_adjustment": fnum(flow_dealer.get("flow_gex_adjustment")),
                "flow_gex_pct_shift": fnum(flow_dealer.get("flow_gex_pct_shift")),
            },
            "authoritative": "settled" if flow_sum.get("flow_direction") in (None, "no_flow") else "live_flow",
        },
        "oi_flow": {
            "prior_snapshot_available": oi_diff.get("prior_snapshot_available"),
            "total_call_oi_change": oi_diff.get("total_call_oi_change"),
            "total_put_oi_change": oi_diff.get("total_put_oi_change"),
            "top_changes": oi_top,
        },
        "term_structure": {
            "by_dte_bucket": by_bucket,
            "by_expiry": by_expiry,
        },
        "volatility": {
            "market_open": vol.get("market_open"),
            "atm_iv": fnum(vol.get("atm_iv")),
            "realized_vol": rv,
            "iv_rv_spreads": vrp,
            "term_structure": vol_term,
            "iv_dispersion": vol.get("iv_dispersion"),
            "skew": skew_rows,
            "put_call_by_expiry": pc_by_exp,
            "put_call_by_moneyness": pc_prof.get("by_moneyness"),
            "oi_concentration": vol.get("oi_concentration"),
            "hedging_scenarios": hedge_scen,
            "liquidity": vol.get("liquidity") or {
                "chain_execution_score": liq.get("chain_execution_score"),
                "best_expiry": liq.get("best_expiry"),
                "thin_expiry_count": liq.get("thin_expiry_count"),
            },
        },
        "qqq_proxy": {
            "spot": qqq_spot,
            "regime": (qqq_sum or {}).get("regime"),
            "gamma_flip": qqq_flip,
            "spot_vs_flip": qqq_vs,
            "net_gex": fnum(((qqq_sum or {}).get("exposures") or {}).get("net_gex")),
            "net_gex_display": fmt_gex(((qqq_sum or {}).get("exposures") or {}).get("net_gex")),
            "call_wall": fnum(QL.get("call_wall")),
            "put_wall": fnum(QL.get("put_wall")),
            "zero_dte_magnet": fnum(QL.get("zero_dte_magnet")),
            "max_positive_gamma": fnum(QL.get("max_positive_gamma")),
            "max_negative_gamma": fnum(QL.get("max_negative_gamma")),
            "pin_score": fnum(qz_pin.get("pin_score") or (qqq_pin or {}).get("live_pin_risk")),
            "magnet": fnum(qz_pin.get("magnet_strike")),
            "max_pain": fnum(qz_pin.get("max_pain") or (qqq_mp or {}).get("max_pain_strike")),
            "em_1sd": fnum(qz_em.get("implied_1sd_dollars")),
            "em_upper": fnum(qz_em.get("upper_bound")),
            "em_lower": fnum(qz_em.get("lower_bound")),
            "zero_dte_pct": fnum(((qqq_sum or {}).get("zero_dte") or {}).get("pct_of_total_gex")),
            "flow_direction": (qqq_flow or {}).get("flow_direction"),
            "flow_gex_pct_shift": fnum((qqq_flow or {}).get("flow_gex_pct_shift")),
            "interpretation": (qqq_sum or {}).get("interpretation"),
            "narrative": {
                "outlook": qn.get("outlook"),
                "regime": qn.get("regime"),
                "key_levels": qn.get("key_levels"),
                "zero_dte": qn.get("zero_dte"),
            },
        },
        "ndx_cross": {
            "spot": ndx_spot,
            "regime": (ndx_sum or {}).get("regime"),
            "gamma_flip": ndx_flip,
            "spot_vs_flip": ndx_vs,
            "net_gex": fnum(((ndx_sum or {}).get("exposures") or {}).get("net_gex")),
            "net_gex_display": fmt_gex(((ndx_sum or {}).get("exposures") or {}).get("net_gex")),
            "call_wall": fnum(NL.get("call_wall")),
            "put_wall": fnum(NL.get("put_wall")),
            "interpretation": (ndx_sum or {}).get("interpretation"),
            "zero_dte": (ndx_sum or {}).get("zero_dte"),
        },
        "vix": {
            "level": fnum(vix.get("vix")),
            "spx_rv_20d": fnum(vix.get("spx_rv_20d")),
            "spread": fnum(vix.get("spread")),
            "ratio": fnum(vix.get("ratio")),
            "state": vix.get("state"),
            "interpretation": vix.get("interpretation"),
        },
        "interpretation": interp,
        "hedging_estimate": hedge,
        "narrative": {
            "regime": narr.get("regime"),
            "gex_change": narr.get("gex_change"),
            "key_levels": narr.get("key_levels"),
            "flow": narr.get("flow"),
            "vanna": narr.get("vanna"),
            "charm": narr.get("charm"),
            "zero_dte": narr.get("zero_dte"),
            "outlook": narr.get("outlook"),
        },
        "narrative_bullets": narrative_bullets,
        "max_pain_by_expiration": mp_by_exp,
        "expected_moves": em_term,
        "scenarios": scenarios,
        "scalp_checklist": [
            "Mark gamma flip as the regime line — acceptance matters more than wicks.",
            "Trade the flip corridor + 0DTE 1σ + nearest ±GEX shelves first; remote 28k/30k walls are context unless extended.",
            "Read local corridor GEX (±500/±1000), not only chain net GEX — far OTM call walls can mask a short-gamma hinge.",
            "If flow is no_flow, settled GEX is boss until contracts_with_flow rises.",
            "Weak pin (<40) = do not fade solely because of magnet; wait for structure + volume.",
            "Watch OI builds on puts below (support/fuel) vs calls above (ceilings).",
            "Short gamma: reduce size into impulsive breaks; never average losers into acceleration pockets.",
            "Cross-check QQQ (cash 0DTE) and NDX regime — disagreement = smaller size / wait.",
            "VIX rich ≠ calm when net/local GEX is negative — premium can stay bid while NQ trends.",
            "Re-pull lean stack after major acceptance away from flip or if spot leaves the 1σ envelope.",
        ],
    }

    data_dir = site / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    latest = data_dir / "latest.json"
    latest.write_text(json.dumps(out, indent=2))
    stamp = now_et.strftime("%Y%m%d_%H%M")
    arch = data_dir / "archive"
    arch.mkdir(exist_ok=True)
    (arch / f"nq_{stamp}.json").write_text(json.dumps(out, indent=2))
    print(
        json.dumps(
            {
                "ok": True,
                "latest": str(latest),
                "spot": spot,
                "flip": flip,
                "regime": regime,
                "bias": bias,
                "profile_points": len(gex_profile),
                "peaks": len(peaks_out),
                "bullets": len(narrative_bullets),
            }
        )
    )


if __name__ == "__main__":
    main()
