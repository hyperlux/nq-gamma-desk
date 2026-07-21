/* NQ Gamma Desk renderer */
(function () {
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  const fmt = (n, d = 2) => {
    if (n == null || Number.isNaN(n)) return "—";
    return Number(n).toLocaleString("en-US", {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
  };

  const fmtInt = (n) => {
    if (n == null || Number.isNaN(n)) return "—";
    return Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
  };

  const fmtSigned = (n, d = 1) => {
    if (n == null || Number.isNaN(n)) return "—";
    const v = Number(n);
    const s = v > 0 ? "+" : "";
    return s + fmt(v, d);
  };

  const toneClass = (tone) => {
    if (tone === "bull") return "bull";
    if (tone === "bear") return "bear";
    if (tone === "warn") return "warn";
    return "muted";
  };

  async function loadData() {
    const res = await fetch(`data/latest.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`Failed to load data/latest.json (${res.status})`);
    return res.json();
  }

  function renderMeta(d) {
    const m = d.meta || {};
    $("#as-of").textContent = m.as_of ? `as of ${m.as_of}` : "as of —";
    $("#generated").textContent = m.generated_at_et || m.generated_at_utc || "—";
    $("#quota").textContent =
      m.remaining != null
        ? `${m.remaining} API left` + (m.requests_this_pull != null ? ` · ${m.requests_this_pull} req` : "")
        : "quota n/a";
    $("#source").textContent = `${m.source || "FlashAlpha"} · ${m.symbol || "NQ=F"}`;
  }

  function renderHero(d) {
    const s = d.spot || {};
    const z = d.zero_dte || {};
    const f = d.flow || {};
    const v = d.vix || {};

    const biasCard = $("#bias-card");
    biasCard.classList.remove("tone-bull", "tone-bear", "tone-warn", "tone-neutral");
    biasCard.classList.add(`tone-${s.bias_tone || "neutral"}`);

    $("#bias-title").textContent = s.bias || "—";
    $("#bias-detail").textContent = s.bias_detail || "";

    $("#spot-price").textContent = fmt(s.price, 2);
    const vs =
      s.spot_vs_flip && s.distance_to_flip != null
        ? `${s.spot_vs_flip} flip by ${fmt(Math.abs(s.distance_to_flip), 1)} pts`
        : "flip n/a";
    $("#spot-sub").textContent = `Regime ${s.local_regime || s.regime || "—"} · ${vs}`;

    $("#stat-gex").textContent = s.net_gex_display || "—";
    $("#stat-gex").className = `v ${s.net_gex != null && s.net_gex < 0 ? "bear" : "bull"}`;

    $("#stat-flip").textContent = fmt(s.gamma_flip, 1);
    $("#stat-em").textContent = z.em_1sd != null ? `±${fmt(z.em_1sd, 0)}` : "—";
    $("#stat-pin").textContent = z.pin_score != null ? `${fmt(z.pin_score, 0)}/100` : "—";
    $("#stat-pin").className = `v ${
      (z.pin_score || 0) >= 40 ? "bull" : (z.pin_score || 0) >= 20 ? "warn" : "muted"
    }`;

    $("#stat-flow").textContent = f.direction || "—";
    $("#stat-flow").className = `v ${f.direction === "no_flow" ? "muted" : "warn"}`;

    $("#stat-vix").textContent = v.level != null ? `${fmt(v.level, 1)} · ${v.state || ""}` : "—";
    $("#stat-vix").className = `v ${v.state === "overvixing" ? "warn" : "muted"}`;

    $("#stat-pain").textContent = d.levels?.max_pain != null ? fmtInt(d.levels.max_pain) : "—";
    $("#stat-magnet").textContent = z.magnet != null ? fmtInt(z.magnet) : "—";
  }

  function renderLadder(d) {
    const ladder = d.ladder || [];
    const track = $("#ladder-track");
    track.innerHTML = "";
    if (!ladder.length) {
      track.innerHTML = `<div class="loading">No levels</div>`;
      return;
    }

    const prices = ladder.map((x) => x.price);
    // pad range so chips aren't on edges
    let min = Math.min(...prices);
    let max = Math.max(...prices);
    const pad = Math.max(40, (max - min) * 0.08);
    min -= pad;
    max += pad;
    const span = max - min || 1;

    // collision avoidance: stack labels slightly if too close in % space
    const placed = [];
    const items = ladder.map((lvl) => {
      let pct = ((max - lvl.price) / span) * 100;
      return { ...lvl, pct };
    });

    // simple vertical de-overlap for chips
    items.sort((a, b) => a.pct - b.pct);
    for (let i = 1; i < items.length; i++) {
      const prev = items[i - 1];
      const cur = items[i];
      const minGap = 4.2; // percent
      if (cur.pct - prev.pct < minGap) {
        cur.pct = prev.pct + minGap;
      }
    }
    // if overflow bottom, compress lightly
    const overflow = items[items.length - 1]?.pct - 98;
    if (overflow > 0) {
      items.forEach((it) => {
        it.pct = Math.max(2, it.pct - overflow * (it.pct / 100));
      });
    }

    for (const lvl of items) {
      const row = document.createElement("div");
      row.className = `ladder-item kind-${lvl.kind}${lvl.emphasis ? " emphasis" : ""}`;
      row.style.top = `${Math.min(98, Math.max(2, lvl.pct))}%`;
      const dist =
        lvl.dist == null ? "" : `<span class="dist">${fmtSigned(lvl.dist, 0)}</span>`;
      row.innerHTML = `
        <div class="price">${fmt(lvl.price, lvl.kind === "flip" || lvl.kind === "spot" ? 1 : 0)}</div>
        <div class="rail">
          <span class="chip" title="${escapeHtml(lvl.note || lvl.label)}">${escapeHtml(
        lvl.label
      )}${dist}</span>
        </div>`;
      track.appendChild(row);
    }

    $("#ladder-note").textContent =
      d.zero_dte?.note ||
      "Levels from FlashAlpha settled OI + 0DTE envelope. Spot line is the live underlying at pull time.";
  }

  function renderScenarios(d) {
    const root = $("#scenarios");
    root.innerHTML = "";
    const list = d.scenarios || [];
    if (!list.length) {
      root.innerHTML = `<div class="loading">No scenarios</div>`;
      return;
    }
    for (const s of list) {
      const el = document.createElement("article");
      el.className = "scenario";
      const tone = s.tone || "neutral";
      const targets =
        (s.targets || []).map((t) => fmtInt(t)).join(" → ") || "—";
      const entry =
        (s.entry_zone || []).length === 2
          ? `${fmtInt(s.entry_zone[0])} – ${fmtInt(s.entry_zone[1])}`
          : (s.entry_zone || []).map(fmtInt).join(" · ") || "—";
      el.innerHTML = `
        <div class="scenario-head">
          <div class="scenario-name"><span class="tag ${tone}">${escapeHtml(
        s.id || ""
      )}</span>${escapeHtml(s.name || "")}</div>
          <span class="tag ${tone}">${escapeHtml(s.side || "")}</span>
        </div>
        <dl>
          <div><dt>Trigger</dt><dd>${escapeHtml(s.trigger || "—")}</dd></div>
          <div><dt>Entry zone</dt><dd class="mono">${escapeHtml(entry)}</dd></div>
          <div><dt>Targets</dt><dd class="mono">${escapeHtml(targets)}</dd></div>
          <div><dt>Invalidation</dt><dd>${escapeHtml(
            s.invalidation_note || (s.invalidation != null ? String(s.invalidation) : "—")
          )}</dd></div>
          <div><dt>Why</dt><dd>${escapeHtml(s.why || "")}</dd></div>
        </dl>`;
      root.appendChild(el);
    }
  }

  function renderPanels(d) {
    const L = d.levels || {};
    const z = d.zero_dte || {};
    const f = d.flow || {};
    const q = d.qqq_proxy || {};
    const v = d.vix || {};
    const n = d.narrative || {};
    const interp = d.interpretation || {};

    $("#kv-levels").innerHTML = kvPairs([
      ["Call wall", fmtInt(L.call_wall)],
      ["Put wall", fmtInt(L.put_wall)],
      ["Gamma flip", fmt(L.gamma_flip, 1)],
      ["Max pain", fmtInt(L.max_pain)],
      ["Max pain expiry", L.max_pain_expiration || "—"],
      ["Max +GEX node", fmtInt(L.max_positive_gamma)],
      ["Max −GEX node", fmtInt(L.max_negative_gamma)],
      ["Highest OI", fmtInt(L.highest_oi_strike)],
      ["0DTE magnet (levels)", fmtInt(L.zero_dte_magnet)],
      ["P/C OI ratio", L.put_call_oi_ratio != null ? fmt(L.put_call_oi_ratio, 2) : "—"],
    ]);

    $("#kv-0dte").innerHTML = kvPairs([
      ["Expiration", z.expiration || "—"],
      ["Market open", String(z.market_open ?? "—")],
      ["Pin score", z.pin_score != null ? `${fmt(z.pin_score, 0)}/100 (${z.pin_quality || "—"})` : "—"],
      ["Magnet", fmtInt(z.magnet)],
      ["0DTE max pain", fmtInt(z.max_pain)],
      ["1σ move", z.em_1sd != null ? `±${fmt(z.em_1sd, 1)} (${fmt(z.em_1sd_pct, 2)}%)` : "—"],
      ["1σ upper", fmt(z.em_upper, 1)],
      ["1σ lower", fmt(z.em_lower, 1)],
      ["ATM IV", z.atm_iv != null ? `${(z.atm_iv * 100).toFixed(1)}%` : "—"],
      ["0DTE net GEX", z.net_gex_display || "—"],
      ["Empty book?", z.empty_book ? "YES — use QQQ proxy" : "no"],
    ]);

    $("#kv-flow").innerHTML = kvPairs([
      ["Direction", f.direction || "—"],
      ["Authoritative", f.authoritative || "—"],
      ["Live GEX", f.live_gex_display || "—"],
      ["GEX shift %", f.flow_gex_pct_shift != null ? fmt(f.flow_gex_pct_shift, 2) : "—"],
      ["Contracts w/ flow", `${f.contracts_with_flow ?? "—"} / ${f.contracts_total ?? "—"}`],
      ["Live flip", fmt(f.live_gamma_flip, 1)],
      ["Live call wall", fmtInt(f.live_call_wall)],
      ["Live put wall", fmtInt(f.live_put_wall)],
      ["Live max pain", fmtInt(f.live_max_pain)],
      ["Live pin", f.live_pin_risk != null ? fmt(f.live_pin_risk, 0) : "—"],
    ]);

    $("#kv-qqq").innerHTML = kvPairs([
      ["QQQ spot", fmt(q.spot, 2)],
      ["QQQ flip", fmt(q.gamma_flip, 2)],
      ["Call wall", fmtInt(q.call_wall)],
      ["Put wall", fmtInt(q.put_wall)],
      ["0DTE magnet", fmtInt(q.zero_dte_magnet)],
      ["Pin score", q.pin_score != null ? fmt(q.pin_score, 0) : "—"],
      ["Max pain", fmtInt(q.max_pain)],
      ["1σ", q.em_1sd != null ? `±${fmt(q.em_1sd, 2)}` : "—"],
    ]);

    $("#kv-vix").innerHTML = kvPairs([
      ["VIX", fmt(v.level, 2)],
      ["SPX RV 20d", fmt(v.spx_rv_20d, 2)],
      ["Spread", fmt(v.spread, 2)],
      ["Ratio", fmt(v.ratio, 2)],
      ["State", v.state || "—"],
    ]);
    $("#vix-interp").textContent = v.interpretation || "";

    $("#narrative").innerHTML = [
      ["Outlook", n.outlook],
      ["Regime", n.regime],
      ["Key levels", n.key_levels],
      ["Vanna", n.vanna],
      ["Charm", n.charm],
      ["0DTE", n.zero_dte],
      ["Flow", n.flow],
      ["Gamma (interp)", interp.gamma],
      ["Vanna (interp)", interp.vanna],
      ["Charm (interp)", interp.charm],
    ]
      .filter(([, val]) => val)
      .map(([k, val]) => `<p><strong>${escapeHtml(k)}:</strong> ${escapeHtml(val)}</p>`)
      .join("");

    const cl = $("#checklist");
    cl.innerHTML = "";
    for (const item of d.scalp_checklist || []) {
      const li = document.createElement("li");
      li.textContent = item;
      cl.appendChild(li);
    }

    // EM table
    const tb = $("#em-body");
    tb.innerHTML = "";
    for (const e of d.expected_moves || []) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(e.expiry || "—")}</td>
        <td>${e.dte ?? "—"}</td>
        <td>${e.atm_iv != null ? (e.atm_iv * 100).toFixed(1) + "%" : "—"}</td>
        <td>${e.move != null ? fmt(e.move, 1) : "—"}</td>
        <td>${e.lower != null ? fmt(e.lower, 1) : "—"}</td>
        <td>${e.upper != null ? fmt(e.upper, 1) : "—"}</td>`;
      tb.appendChild(tr);
    }

    $("#disclaimer").textContent = d.meta?.disclaimer || "";
  }

  function kvPairs(rows) {
    return rows
      .map(
        ([k, v]) =>
          `<div class="k">${escapeHtml(k)}</div><div class="v">${escapeHtml(String(v))}</div>`
      )
      .join("");
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  async function main() {
    const root = $("#app");
    try {
      const data = await loadData();
      renderMeta(data);
      renderHero(data);
      renderLadder(data);
      renderScenarios(data);
      renderPanels(data);
      $("#app").hidden = false;
      $("#boot").hidden = true;
    } catch (err) {
      $("#boot").innerHTML = `<div class="error">Could not load desk data: ${escapeHtml(
        err.message
      )}</div>`;
    }
  }

  main();
})();
