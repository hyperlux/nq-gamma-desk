# NQ Gamma Desk

Live **NQ=F** gamma / dealer-positioning scalping board, fed by FlashAlpha pulls from Hermes.

**Site:** https://hyperlux.github.io/nq-gamma-desk/

## What you get

- Day bias from spot vs gamma flip + net GEX
- Visual level ladder (walls, flip, max pain, 0DTE magnet, ±1σ)
- Three scalp scenarios with triggers / targets / invalidation
- 0DTE structure, live flow, QQQ proxy, VIX regime, narrative
- Checklist tuned for short-gamma / flip-zone days

## Data flow

1. Hermes pulls FlashAlpha (`levels`, `summary`, `zero-dte`, flow, …) into  
   `/home/clawdbot/systems/trading/nq_report_YYYYMMDD_HHMMSS/raw/`
2. `scripts/export_latest.py` → `data/latest.json`
3. `scripts/publish_desk.sh` commits + pushes → GitHub Pages

```bash
# From a report directory
./scripts/publish_desk.sh /home/clawdbot/systems/trading/nq_report_20260721_071947
```

The static UI only reads `data/latest.json` (no API keys in the browser).

## Privacy

Repo is **public** so GitHub Pages is free/simple. It contains **derived levels and a gameplan**, not your FlashAlpha API key. Do not commit `.env` or raw API keys.

## Disclaimer

Not investment advice. Model output from FlashAlpha; futures options via Black-76.
