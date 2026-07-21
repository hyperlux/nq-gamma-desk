/* NQ Gamma Desk renderer — full-stack FlashAlpha board */
(function () {
  const $ = (sel, el = document) => el.querySelector(sel);

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

  const fmtGex = (n) => {
    if (n == null || Number.isNaN(n)) return "—";
    const x = Number(n);
    const sign = x > 0 ? "+" : x < 0 ? "-" : "";
    const ax = Math.abs(x);
    if (ax >= 1e9) return `${sign}${(ax / 1e9).toFixed(2)}B`;
    if (ax >= 1e6) return `${sign}${(ax / 1e6).toFixed(2)}M`;
    if (ax >= 1e3) return `${sign}${(ax / 1e3).toFixed(1)}K`;
    return `${sign}${ax.toFixed(0)}`;
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
    $("#depth").textContent = m.depth ? `${m.depth} pull` : "lean";
  }

  function renderHero(d) {
    const s = d.spot || {};
    const z = d.zero_dte || {};
    const f = d.flow || {};
    const v = d.vix || {};
    const vol = d.volatility || {};

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
    $("#session-note").textContent = d.meta?.session_note || "";

    $("#stat-gex").textContent = s.net_gex_display || "—";
    $("#stat-gex").className = `v ${s.net_gex != null && s.net_gex < 0 ? "bear" : "bull"}`;

    const loc = s.local_corridor_1000 || {};
    $("#stat-local").textContent = loc.net_gex_display || "—";
    $("#stat-local").className = `v ${loc.net_gex != null && loc.net_gex < 0 ? "bear" : "bull"}`;

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
    $("#stat-dex").textContent = s.net_dex_display || "—";
    $("#stat-vex").textContent = s.net_vex_display || "—";
    $("#stat-iv").textContent = vol.atm_iv != null ? `${fmt(vol.atm_iv, 1)}%` : "—";
  }

  function renderBullets(d) {
    const root = $("#narrative-bullets");
    root.innerHTML = "";
    const bullets = d.narrative_bullets || [];
    if (!bullets.length) {
      root.innerHTML = `<p class="section-note">No narrative bullets in this pull.</p>`;
      return;
    }
    for (const b of bullets) {
      const el = document.createElement("div");
      el.className = "bullet";
      // light markdown **bold**
      el.innerHTML = escapeHtml(b).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      root.appendChild(el);
    }
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
    let min = Math.min(...prices);
    let max = Math.max(...prices);
    const pad = Math.max(40, (max - min) * 0.08);
    min -= pad;
    max += pad;
    const span = max - min || 1;

    const items = ladder.map((lvl) => {
      let pct = ((max - lvl.price) / span) * 100;
      return { ...lvl, pct };
    });

    items.sort((a, b) => a.pct - b.pct);
    for (let i = 1; i < items.length; i++) {
      const prev = items[i - 1];
      const cur = items[i];
      const minGap = 3.6;
      if (cur.pct - prev.pct < minGap) cur.pct = prev.pct + minGap;
    }
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
      const dist = lvl.dist == null ? "" : `<span class="dist">${fmtSigned(lvl.dist, 0)}</span>`;
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
      "Levels from FlashAlpha settled OI + 0DTE envelope + nearest GEX nodes.";
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
      const targets = (s.targets || []).map((t) => fmtInt(t)).join(" → ") || "—";
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
          ${
            s.management
              ? `<div><dt>Manage</dt><dd>${escapeHtml(s.management)}</dd></div>`
              : ""
          }
        </dl>`;
      root.appendChild(el);
    }
  }

  function renderGexChart(d) {
    const root = $("#gex-chart");
    const profile = d.gex_map?.profile || [];
    const spot = d.spot?.price;
    const flip = d.spot?.gamma_flip;
    root.innerHTML = "";
    if (!profile.length) {
      root.innerHTML = `<div class="loading">No GEX profile</div>`;
      return;
    }
    const maxAbs = Math.max(...profile.map((p) => Math.abs(p.net_gex || 0)), 1);
    const chart = document.createElement("div");
    chart.className = "gex-bars";
    for (const p of profile) {
      const col = document.createElement("div");
      col.className = "gex-col";
      const h = Math.max(4, (Math.abs(p.net_gex) / maxAbs) * 100);
      const pos = (p.net_gex || 0) >= 0;
      const isSpot = spot != null && Math.abs(p.strike - spot) < 30;
      const isFlip = flip != null && Math.abs(p.strike - flip) < 30;
      col.innerHTML = `
        <div class="bar-wrap">
          <div class="bar ${pos ? "pos" : "neg"}${isSpot ? " spot" : ""}${isFlip ? " flip" : ""}"
               style="height:${h}%"
               title="${fmtInt(p.strike)} · ${p.net_gex_display || fmtGex(p.net_gex)}"></div>
        </div>
        <div class="lbl">${p.strike % 100 === 0 || isSpot || isFlip ? fmtInt(p.strike) : ""}</div>`;
      chart.appendChild(col);
    }
    root.appendChild(chart);
    const noteBits = [];
    if (d.spot?.local_corridor_500)
      noteBits.push(`±500 corridor ${d.spot.local_corridor_500.net_gex_display}`);
    if (d.spot?.local_corridor_1000)
      noteBits.push(`±1000 corridor ${d.spot.local_corridor_1000.net_gex_display}`);
    $("#gex-profile-note").textContent = noteBits.join(" · ") || "Net GEX by strike near spot";
  }

  function strikeTable(rows, opts = {}) {
    if (!rows || !rows.length) return `<div class="section-note">No rows</div>`;
    const head = opts.head || ["Strike", "Net GEX", "Call OI", "Put OI"];
    const body = rows
      .map((r) => {
        const g = r.net_gex_display || fmtGex(r.net_gex);
        const cls = (r.net_gex || 0) < 0 ? "bear" : "bull";
        const extra = opts.extra
          ? opts.extra(r)
          : `<td class="mono">${r.call_oi ?? "—"}</td><td class="mono">${r.put_oi ?? "—"}</td>`;
        return `<tr>
          <td class="mono">${fmtInt(r.strike)}</td>
          <td class="mono ${cls}">${escapeHtml(g)}</td>
          ${extra}
        </tr>`;
      })
      .join("");
    return `<table class="mini"><thead><tr>${head
      .map((h) => `<th>${escapeHtml(h)}</th>`)
      .join("")}</tr></thead><tbody>${body}</tbody></table>`;
  }

  function renderTables(d) {
    const gm = d.gex_map || {};
    $("#pos-near").innerHTML = strikeTable(gm.positive_near || []);
    $("#neg-near").innerHTML = strikeTable(gm.negative_near || []);

    const peaks = gm.peaks || [];
    $("#peaks-table").innerHTML = strikeTable(peaks, {
      head: ["Strike", "Net GEX", "Side", "Dist"],
      extra: (r) =>
        `<td>${escapeHtml(r.side || "—")}</td><td class="mono">${fmtSigned(r.dist, 0)}</td>`,
    });

    const oi = d.oi_flow || {};
    $("#kv-oi-totals").innerHTML = kvPairs([
      ["Call ΔOI", oi.total_call_oi_change ?? "—"],
      ["Put ΔOI", oi.total_put_oi_change ?? "—"],
      ["Prior snap", String(oi.prior_snapshot_available ?? "—")],
    ]);
    const oiRows = oi.top_changes || [];
    if (!oiRows.length) {
      $("#oi-table").innerHTML = `<div class="section-note">No OI diff</div>`;
    } else {
      $("#oi-table").innerHTML = `<table class="mini"><thead><tr>
        <th>Strike</th><th>Type</th><th>Expiry</th><th>ΔOI</th><th>Today</th>
      </tr></thead><tbody>
      ${oiRows
        .map((r) => {
          const cls = (r.oi_change || 0) >= 0 ? "bull" : "bear";
          return `<tr>
            <td class="mono">${fmtInt(r.strike)}</td>
            <td>${escapeHtml(r.type || "")}</td>
            <td class="mono">${escapeHtml(r.expiry || "")}</td>
            <td class="mono ${cls}">${fmtSigned(r.oi_change, 0)}</td>
            <td class="mono">${fmtInt(r.today_oi)}</td>
          </tr>`;
        })
        .join("")}
      </tbody></table>`;
    }
  }

  function renderTerm(d) {
    const ts = d.term_structure || {};
    const buckets = ts.by_dte_bucket || [];
    const root = $("#term-bars");
    root.innerHTML = "";
    if (!buckets.length) {
      root.innerHTML = `<div class="section-note">No term buckets</div>`;
    } else {
      const maxAbs = Math.max(...buckets.map((b) => Math.abs(b.net_gex || 0)), 1);
      for (const b of buckets) {
        const row = document.createElement("div");
        row.className = "term-row";
        const pct = Math.max(6, (Math.abs(b.net_gex || 0) / maxAbs) * 100);
        const cls = (b.net_gex || 0) < 0 ? "neg" : "pos";
        row.innerHTML = `
          <div class="term-lab">${escapeHtml(b.bucket || "")}</div>
          <div class="term-track"><div class="term-fill ${cls}" style="width:${pct}%"></div></div>
          <div class="term-val mono ${cls}">${escapeHtml(b.net_gex_display || fmtGex(b.net_gex))}</div>`;
        root.appendChild(row);
      }
    }

    const exps = (ts.by_expiry || []).slice(0, 8);
    $("#term-expiry").innerHTML = exps.length
      ? `<table class="mini"><thead><tr>
          <th>Expiry</th><th>DTE</th><th>GEX</th><th>% chain</th>
        </tr></thead><tbody>
        ${exps
          .map((e) => {
            const cls = (e.net_gex || 0) < 0 ? "bear" : "bull";
            return `<tr>
              <td class="mono">${escapeHtml(e.expiration || "")}</td>
              <td class="mono">${e.dte ?? "—"}</td>
              <td class="mono ${cls}">${escapeHtml(e.net_gex_display || fmtGex(e.net_gex))}</td>
              <td class="mono">${e.pct_of_chain_gex != null ? fmt(e.pct_of_chain_gex, 1) + "%" : "—"}</td>
            </tr>`;
          })
          .join("")}
        </tbody></table>`
      : "";
  }

  function renderVol(d) {
    const vol = d.volatility || {};
    const rv = vol.realized_vol || {};
    const vrp = vol.iv_rv_spreads || {};
    const term = vol.term_structure || {};
    const liq = vol.liquidity || {};
    $("#kv-vol").innerHTML = kvPairs([
      ["ATM IV", vol.atm_iv != null ? `${fmt(vol.atm_iv, 2)}%` : "—"],
      ["RV 5/10/20", `${fmt(rv.rv_5d, 1)} / ${fmt(rv.rv_10d, 1)} / ${fmt(rv.rv_20d, 1)}`],
      ["VRP 20d", vrp.vrp_20d != null ? fmt(vrp.vrp_20d, 2) : "—"],
      ["VRP assess", vrp.assessment || "—"],
      ["IV term", term.state || "—"],
      ["Near slope", term.near_slope_pct != null ? `${fmt(term.near_slope_pct, 2)}%` : "—"],
      ["OI top3%", vol.oi_concentration?.top_3_pct != null ? `${vol.oi_concentration.top_3_pct}%` : "—"],
      ["ATM spread", liq.atm_avg_spread_pct != null ? `${fmt(liq.atm_avg_spread_pct, 2)}%` : liq.chain_execution_score != null ? `score ${liq.chain_execution_score}` : "—"],
    ]);

    const skew = vol.skew || [];
    $("#skew-table").innerHTML = skew.length
      ? `<table class="mini"><thead><tr>
          <th>Expiry</th><th>DTE</th><th>ATM</th><th>25d skew</th><th>P10</th><th>C10</th>
        </tr></thead><tbody>
        ${skew
          .slice(0, 6)
          .map(
            (s) => `<tr>
            <td class="mono">${escapeHtml(s.expiry || "")}</td>
            <td class="mono">${s.dte ?? "—"}</td>
            <td class="mono">${s.atm_iv != null ? fmt(s.atm_iv, 1) : "—"}</td>
            <td class="mono">${s.skew_25d != null ? fmt(s.skew_25d, 2) : "—"}</td>
            <td class="mono">${s.put_10d_iv != null ? fmt(s.put_10d_iv, 1) : "—"}</td>
            <td class="mono">${s.call_10d_iv != null ? fmt(s.call_10d_iv, 1) : "—"}</td>
          </tr>`
          )
          .join("")}
        </tbody></table>`
      : `<div class="section-note">No skew rows</div>`;

    const pc = vol.put_call_by_expiry || [];
    $("#pc-table").innerHTML = pc.length
      ? `<h3 class="mini-h">Put/Call by expiry</h3><table class="mini"><thead><tr>
          <th>Expiry</th><th>P/C OI</th><th>P/C Vol</th><th>Put OI</th><th>Call OI</th>
        </tr></thead><tbody>
        ${pc
          .slice(0, 8)
          .map(
            (r) => `<tr>
            <td class="mono">${escapeHtml(r.expiry || "")}</td>
            <td class="mono">${r.pc_ratio_oi != null ? fmt(r.pc_ratio_oi, 2) : "—"}</td>
            <td class="mono">${r.pc_ratio_volume != null ? fmt(r.pc_ratio_volume, 2) : "—"}</td>
            <td class="mono">${fmtInt(r.put_oi)}</td>
            <td class="mono">${fmtInt(r.call_oi)}</td>
          </tr>`
          )
          .join("")}
        </tbody></table>`
      : "";

    const hs = vol.hedging_scenarios || [];
    $("#hedge-table").innerHTML = hs.length
      ? `<h3 class="mini-h">Dealer hedge if spot moves</h3><table class="mini"><thead><tr>
          <th>Move</th><th>Dir</th><th>Shares</th><th>Notional</th>
        </tr></thead><tbody>
        ${hs
          .map((h) => {
            const cls = h.direction === "sell" ? "bear" : "bull";
            return `<tr>
              <td class="mono">${h.move_pct > 0 ? "+" : ""}${h.move_pct}%</td>
              <td class="${cls}">${escapeHtml(h.direction || "")}</td>
              <td class="mono">${fmtInt(h.dealer_shares)}</td>
              <td class="mono ${cls}">${escapeHtml(h.notional_display || fmtGex(h.notional_usd))}</td>
            </tr>`;
          })
          .join("")}
        </tbody></table>`
      : "";
  }

  function renderPanels(d) {
    const L = d.levels || {};
    const z = d.zero_dte || {};
    const f = d.flow || {};
    const q = d.qqq_proxy || {};
    const n = d.narrative || {};
    const interp = d.interpretation || {};
    const ndx = d.ndx_cross || {};
    const v = d.vix || {};

    $("#kv-levels").innerHTML = kvPairs([
      ["Call wall", fmtInt(L.call_wall)],
      ["Put wall", fmtInt(L.put_wall)],
      ["Gamma flip", fmt(L.gamma_flip, 1)],
      ["Max pain", fmtInt(L.max_pain)],
      ["Max pain signal", L.max_pain_signal || "—"],
      ["Pin probability", L.pin_probability != null ? `${fmt(L.pin_probability, 0)}%` : "—"],
      ["Max +GEX node", fmtInt(L.max_positive_gamma)],
      ["Max −GEX node", fmtInt(L.max_negative_gamma)],
      ["Highest OI", fmtInt(L.highest_oi_strike)],
      ["LIS", L.lis?.strike != null ? fmtInt(L.lis.strike) : "—"],
      ["P/C OI ratio", L.put_call_oi_ratio != null ? fmt(L.put_call_oi_ratio, 2) : "—"],
      ["OpEx / TW", `${L.is_opex ? "yes" : "no"} / ${L.is_triple_witching ? "yes" : "no"}`],
    ]);

    $("#kv-0dte").innerHTML = kvPairs([
      ["Expiration", z.expiration || "—"],
      ["Market open", String(z.market_open ?? "—")],
      ["TTC (hrs)", z.time_to_close_hours != null ? fmt(z.time_to_close_hours, 2) : "—"],
      ["Pin score", z.pin_score != null ? `${fmt(z.pin_score, 0)}/100 (${z.pin_quality || "—"})` : "—"],
      ["Magnet", fmtInt(z.magnet)],
      ["0DTE max pain", fmtInt(z.max_pain)],
      ["1σ move", z.em_1sd != null ? `±${fmt(z.em_1sd, 1)} (${fmt(z.em_1sd_pct, 2)}%)` : "—"],
      ["1σ upper", fmt(z.em_upper, 1)],
      ["1σ lower", fmt(z.em_lower, 1)],
      [
        "ATM IV",
        z.atm_iv != null ? (z.atm_iv < 3 ? `${(z.atm_iv * 100).toFixed(1)}%` : `${fmt(z.atm_iv, 1)}%`) : "—",
      ],
      ["0DTE net GEX", z.net_gex_display || "—"],
      ["% of total GEX", z.pct_of_total_gex != null ? fmt(z.pct_of_total_gex, 1) : "—"],
      ["Empty book?", z.empty_book ? "YES — use QQQ proxy" : "no"],
    ]);

    const dr = f.dealer_risk || {};
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
    $("#flow-dealer-note").textContent = dr.description || "";

    $("#kv-qqq").innerHTML = kvPairs([
      ["QQQ spot", fmt(q.spot, 2)],
      ["Regime", q.regime || "—"],
      ["vs flip", q.spot_vs_flip || "—"],
      ["QQQ flip", fmt(q.gamma_flip, 2)],
      ["Net GEX", q.net_gex_display || "—"],
      ["Call wall", fmtInt(q.call_wall)],
      ["Put wall", fmtInt(q.put_wall)],
      ["0DTE magnet", fmtInt(q.zero_dte_magnet)],
      ["Pin score", q.pin_score != null ? fmt(q.pin_score, 0) : "—"],
      ["Max pain", fmtInt(q.max_pain)],
      ["1σ", q.em_1sd != null ? `±${fmt(q.em_1sd, 2)}` : "—"],
      ["0DTE % GEX", q.zero_dte_pct != null ? `${fmt(q.zero_dte_pct, 1)}%` : "—"],
      ["Flow", q.flow_direction || "—"],
    ]);
    const qn = q.narrative || {};
    $("#qqq-narr").textContent = [qn.outlook, qn.key_levels, qn.zero_dte].filter(Boolean).join(" · ");

    $("#kv-ndx").innerHTML = kvPairs([
      ["NDX spot", fmt(ndx.spot, 1)],
      ["Regime", ndx.regime || "—"],
      ["vs flip", ndx.spot_vs_flip || "—"],
      ["Flip", fmt(ndx.gamma_flip, 1)],
      ["Net GEX", ndx.net_gex_display || "—"],
      ["Call wall", fmtInt(ndx.call_wall)],
      ["Put wall", fmtInt(ndx.put_wall)],
    ]);
    const ni = ndx.interpretation || {};
    $("#ndx-interp").textContent = [ni.gamma, ni.vanna, ni.charm].filter(Boolean).join(" · ");

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
      ["GEX change", n.gex_change],
      ["Gamma (interp)", interp.gamma],
      ["Vanna (interp)", interp.vanna],
      ["Charm (interp)", interp.charm],
      ["Alignment", L.dealer_alignment?.description],
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

    const tb = $("#em-body");
    tb.innerHTML = "";
    for (const e of d.expected_moves || []) {
      const tr = document.createElement("tr");
      const iv =
        e.atm_iv == null ? "—" : e.atm_iv < 3 ? `${(e.atm_iv * 100).toFixed(1)}%` : `${fmt(e.atm_iv, 1)}%`;
      tr.innerHTML = `
        <td>${escapeHtml(e.expiry || "—")}</td>
        <td>${e.dte ?? "—"}</td>
        <td>${iv}</td>
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
    try {
      const data = await loadData();
      renderMeta(data);
      renderHero(data);
      renderBullets(data);
      renderLadder(data);
      renderScenarios(data);
      renderGexChart(data);
      renderTables(data);
      renderTerm(data);
      renderVol(data);
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
