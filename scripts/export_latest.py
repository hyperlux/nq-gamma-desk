#!/usr/bin/env python3
"""Export a FlashAlpha NQ report directory (raw/*.json) into site data/latest.json.

Usage:
  python3 export_latest.py /path/to/nq_report_YYYYMMDD_HHMMSS [/path/to/site]
"""
from __future__ import annotations

import json
import pathlib
import sys
import datetime
from zoneinfo import ZoneInfo


def load(raw: pathlib.Path, name: str):
    p = raw / f"{name}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


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
    qqq_zdte = load(raw, "qqq_zero_dte") or {}
    qqq_lv = load(raw, "qqq_levels") or {}
    vix = load(raw, "vix") or {}

    L = levels.get("levels") or {}
    spot = fnum(levels.get("underlying_price") or summary.get("underlying_price"))
    flip = fnum(L.get("gamma_flip") or summary.get("gamma_flip"))
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
    net_gex = fnum(exposures.get("net_gex"))
    net_dex = fnum(exposures.get("net_dex"))
    net_vex = fnum(exposures.get("net_vex"))
    net_chex = fnum(exposures.get("net_chex"))
    regime = summary.get("regime") or "unknown"
    interp = summary.get("interpretation") or {}
    hedge = summary.get("hedging_estimate") or {}

    # Local regime priority: spot vs flip
    if vs_flip == "below":
        local_regime = "negative_gamma"
    elif vs_flip == "above":
        local_regime = "positive_gamma"
    else:
        local_regime = str(regime)

    if vs_flip == "below" and dist_flip is not None and abs(dist_flip) < 50:
        bias = "FLIP-ZONE / NEGATIVE GAMMA"
        bias_detail = "Two-way risk at the hinge — small acceptance away from flip can trend."
        bias_tone = "warn"  # amber
    elif vs_flip == "below":
        bias = "BELOW FLIP / NEGATIVE GAMMA"
        bias_detail = "Dealers short gamma below flip — moves can amplify; favor momentum over mean-revert."
        bias_tone = "bear"
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
    atm_iv = fnum(zd_em.get("atm_iv"))

    nq_0dte_empty = bool(zdte.get("no_zero_dte"))
    if not nq_0dte_empty:
        # empty-book heuristic
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

    narr = narrative.get("narrative") if isinstance(narrative.get("narrative"), dict) else {}
    if not narr and isinstance(narrative, dict) and "regime" in narrative:
        narr = narrative

    QL = (qqq_lv or {}).get("levels") or {}
    qz_pin = (qqq_zdte or {}).get("pin_risk") or {}
    qz_em = (qqq_zdte or {}).get("expected_move") or {}
    qqq_spot = fnum((qqq_lv or {}).get("underlying_price"))

    ems = em.get("expected_moves") or []
    em_term = []
    for e in ems[:10]:
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

    # Build ladder levels for viz (unique, sorted)
    ladder = []

    def add_lvl(price, label, kind, emphasis=False, note=None):
        if price is None:
            return
        ladder.append(
            {
                "price": float(price),
                "label": label,
                "kind": kind,  # call_wall|put_wall|flip|pain|magnet|spot|em_up|em_dn|pos_gex|neg_gex|oi
                "emphasis": bool(emphasis),
                "note": note,
                "dist": None if spot is None else float(price) - float(spot),
            }
        )

    add_lvl(call_wall, "Call wall", "call_wall", True, "Remote resistance / dealer call concentration")
    add_lvl(max_pos, "Max +GEX", "pos_gex", False, "Local positive gamma node")
    add_lvl(em_up, "0DTE +1σ", "em_up", True, "Same-day upper expected move")
    add_lvl(magnet, "0DTE magnet", "magnet", pin_quality in ("hard", "moderate"), f"Pin score {pin_score:.0f}/100 — {pin_quality}")
    add_lvl(mp, "Max pain", "pain", True, f"Expiry {mp_exp}" if mp_exp else None)
    add_lvl(flip, "Gamma flip", "flip", True, "Regime line — primary hinge")
    add_lvl(spot, "Spot", "spot", True, "Last underlying")
    add_lvl(zd_mp, "0DTE max pain", "pain", False, "Same-day pain")
    add_lvl(em_dn, "0DTE −1σ", "em_dn", True, "Same-day lower expected move")
    add_lvl(max_neg, "Max −GEX", "neg_gex", False, "Local negative gamma node")
    add_lvl(put_wall, "Put wall", "put_wall", True, "Remote support / dealer put concentration")
    add_lvl(hi_oi, "Highest OI", "oi", False, "Peak open interest strike")

    # de-dupe near-identical prices (within 0.5 pt) keeping emphasis
    ladder.sort(key=lambda x: -x["price"])
    deduped = []
    for item in ladder:
        if deduped and abs(deduped[-1]["price"] - item["price"]) < 0.75:
            # merge labels if different kinds
            if item["kind"] != deduped[-1]["kind"]:
                deduped[-1]["label"] = f"{deduped[-1]['label']} · {item['label']}"
                deduped[-1]["emphasis"] = deduped[-1]["emphasis"] or item["emphasis"]
            continue
        deduped.append(item)
    ladder = deduped

    # Scenarios for scalping
    scenarios = []
    if spot is not None and flip is not None:
        scenarios.append(
            {
                "id": "A",
                "name": "Flip reclaim & hold",
                "side": "long",
                "tone": "bull",
                "trigger": f"15–30m acceptance above ~{flip+25:.0f}–{flip+55:.0f} after clearing flip",
                "entry_zone": [round(flip + 20), round(flip + 60)],
                "targets": [
                    round(mp) if mp else None,
                    round(em_up) if em_up else None,
                    round(magnet) if magnet else None,
                ],
                "invalidation": round(spot - 40) if spot else None,
                "invalidation_note": f"Back below ~{spot-25:.0f} with momentum",
                "why": "Leaving the negative-gamma hinge reduces forced dealer sell-rallies; pain/magnet sit overhead.",
            }
        )
        scenarios.append(
            {
                "id": "B",
                "name": "Flip reject / downside expansion",
                "side": "short",
                "tone": "bear",
                "trigger": f"Failure at flip and acceptance below ~{spot-45:.0f}–{spot-75:.0f}",
                "entry_zone": [round(spot - 80), round(spot - 40)],
                "targets": [
                    round(em_dn) if em_dn else None,
                    round(max_neg) if max_neg else None,
                ],
                "invalidation": round(flip + 50) if flip else None,
                "invalidation_note": f"Swift reclaim >{flip+50:.0f}",
                "why": "Short gamma can accelerate dips; no hard put wall until remote put wall.",
            }
        )
        scenarios.append(
            {
                "id": "C",
                "name": "Chop / mean-test (base pre-flow)",
                "side": "range",
                "tone": "neutral",
                "trigger": f"Price holds inside 0DTE 1σ with tests of flip / max pain; flow still quiet",
                "entry_zone": [round(em_dn) if em_dn else None, round(em_up) if em_up else None],
                "targets": [round(flip) if flip else None, round(mp) if mp else None],
                "invalidation": None,
                "invalidation_note": "Impulsive break beyond 1σ with rising live flow shift",
                "why": f"Pin quality is {pin_quality} ({pin_score:.0f}/100) — do not lean on magnet as a hard pin day.",
            }
        )

    # Clean None targets
    for s in scenarios:
        s["targets"] = [t for t in s["targets"] if t is not None]
        if s["entry_zone"] and any(x is None for x in s["entry_zone"]):
            s["entry_zone"] = [x for x in s["entry_zone"] if x is not None]

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_et = datetime.datetime.now(ZoneInfo("America/New_York"))

    # fetch count from log if present
    reqs = None
    flog = report / "fetch_log.tsv"
    if flog.exists():
        reqs = sum(1 for line in flog.read_text().splitlines() if line.strip())

    out = {
        "meta": {
            "symbol": "NQ=F",
            "title": "NQ Gamma Desk",
            "generated_at_utc": now_utc.isoformat(),
            "generated_at_et": now_et.strftime("%Y-%m-%d %H:%M %Z"),
            "as_of": levels.get("as_of") or summary.get("as_of"),
            "source": "FlashAlpha",
            "report_dir": str(report),
            "plan": account.get("plan"),
            "usage_today": account.get("usage_today"),
            "remaining": account.get("remaining"),
            "requests_this_pull": reqs,
            "disclaimer": "Not investment advice. Dealer-positioning model from FlashAlpha; NQ options-on-futures via Black-76.",
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
        },
        "ladder": ladder,
        "zero_dte": {
            "expiration": zdte.get("expiration"),
            "market_open": zdte.get("market_open"),
            "time_to_close_hours": zdte.get("time_to_close_hours"),
            "regime": zdte.get("regime"),
            "net_gex": fnum(zd_exp.get("net_gex")),
            "net_gex_display": fmt_gex(zd_exp.get("net_gex")),
            "pct_of_total_gex": fnum(zd_exp.get("pct_of_total_gex")),
            "pin_score": pin_score,
            "pin_quality": pin_quality,
            "magnet": magnet,
            "max_pain": zd_mp,
            "em_1sd": em_1sd,
            "em_1sd_pct": em_pct,
            "em_upper": em_up,
            "em_lower": em_dn,
            "atm_iv": atm_iv,
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
            "live_gamma_flip": fnum(flow_lv.get("live_gamma_flip")),
            "live_call_wall": fnum(flow_lv.get("live_call_wall")),
            "live_put_wall": fnum(flow_lv.get("live_put_wall")),
            "live_max_pain": fnum(flow_lv.get("live_max_pain")),
            "live_pin_risk": fnum(flow_pin.get("live_pin_risk")),
            "magnet_strike": fnum(flow_pin.get("magnet_strike")),
            "authoritative": "settled" if flow_sum.get("flow_direction") in (None, "no_flow") else "live_flow",
        },
        "qqq_proxy": {
            "spot": qqq_spot,
            "gamma_flip": fnum(QL.get("gamma_flip")),
            "call_wall": fnum(QL.get("call_wall")),
            "put_wall": fnum(QL.get("put_wall")),
            "zero_dte_magnet": fnum(QL.get("zero_dte_magnet")),
            "max_positive_gamma": fnum(QL.get("max_positive_gamma")),
            "max_negative_gamma": fnum(QL.get("max_negative_gamma")),
            "pin_score": fnum(qz_pin.get("pin_score")),
            "magnet": fnum(qz_pin.get("magnet_strike")),
            "max_pain": fnum(qz_pin.get("max_pain")),
            "em_1sd": fnum(qz_em.get("implied_1sd_dollars")),
            "em_upper": fnum(qz_em.get("upper_bound")),
            "em_lower": fnum(qz_em.get("lower_bound")),
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
        "expected_moves": em_term,
        "scenarios": scenarios,
        "scalp_checklist": [
            "Mark gamma flip as the regime line — acceptance matters more than wicks.",
            "Trade the flip corridor + 0DTE 1σ + max pain first; remote 28k/30k walls are day-trade noise unless extended.",
            "If flow is no_flow, settled GEX is boss until contracts_with_flow rises after cash open.",
            "Weak pin (<40) = do not fade solely because of magnet; wait for structure.",
            "Short gamma: reduce size into impulsive breaks; avoid averaging losers into acceleration.",
            "VIX rich ≠ calm when net GEX is negative — premium can stay bid while NQ trends.",
            "Re-pull lean stack after NY open if levels look stale or spot left the corridor.",
        ],
    }

    data_dir = site / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    latest = data_dir / "latest.json"
    latest.write_text(json.dumps(out, indent=2))
    # also archive by date
    stamp = now_et.strftime("%Y%m%d_%H%M")
    arch = data_dir / "archive"
    arch.mkdir(exist_ok=True)
    (arch / f"nq_{stamp}.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({"ok": True, "latest": str(latest), "spot": spot, "flip": flip, "regime": regime, "bias": bias}))


if __name__ == "__main__":
    main()
