/* NetWatch dashboard. Polls the Flask API; all text is inserted with textContent. */
"use strict";
const $ = (id) => document.getElementById(id);
const LAV = "#9b87f5", GOLD = "#f2c14e", OK = "#4ade80", BAD = "#f87171";
let failures = 0, loadedConfig = false;

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
const fmt = (v, unit, d = 1) => (v === null || v === undefined ? "Unavailable" : (typeof v === "number" ? v.toFixed(d) : v) + (unit ? " " + unit : ""));
function bytes(n) {
  if (n === null || n === undefined) return "Unavailable";
  const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0;
  while (n >= 1024 && i < 4) { n /= 1024; i++; }
  return (i ? n.toFixed(2) : n) + " " + u[i];
}
async function api(path, opts) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({ error: "Bad response" }));
  if (!r.ok) { const e = new Error(data.error || "Request failed"); e.details = data.details; throw e; }
  return data;
}
function setCard(id, cls) {
  const c = $(id); c.classList.remove("state-ok", "state-warn", "state-bad"); if (cls) c.classList.add("state-" + cls);
}
function setState(id, text, cls) { const e = $(id); e.textContent = text; e.className = "big " + cls; }

/* ---------- tabs ---------- */
$("tabs").addEventListener("click", (ev) => {
  const t = ev.target.closest(".tab"); if (!t) return;
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === t));
  document.querySelectorAll(".tabpanel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + t.dataset.tab));
  if (t.dataset.tab === "info") loadInfo();
  if (t.dataset.tab === "config") loadConfig();
  if (t.dataset.tab === "dashboard") refreshHistory();
});

/* ---------- charts (plain canvas, no external library) ---------- */
function drawChart(canvas, series, opts) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight || +canvas.getAttribute("height");
  canvas.width = w * dpr; canvas.height = h * dpr;
  const g = canvas.getContext("2d"); g.scale(dpr, dpr); g.clearRect(0, 0, w, h);
  const L = 44, R = 10, T = 12, B = 22, pw = w - L - R, ph = h - T - B;
  const pts = series.flatMap((s) => s.points.filter((p) => p.v !== null).map((p) => p.v));
  let max = Math.max(opts.minMax || 1, ...pts) * 1.15;
  g.font = "11px Segoe UI, Arial"; g.fillStyle = "#9a95b8"; g.strokeStyle = "rgba(155,135,245,.15)"; g.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = T + ph - (ph * i) / 4;
    g.beginPath(); g.moveTo(L, y); g.lineTo(w - R, y); g.stroke();
    g.fillText((max * i / 4).toFixed(max < 10 ? 1 : 0), 6, y + 4);
  }
  const win = opts.window;
  g.fillText("-" + (win >= 60 ? win / 60 + " min" : win + " s"), L, h - 6);
  g.textAlign = "right"; g.fillText("now", w - R, h - 6); g.textAlign = "left";
  if (opts.threshold && opts.threshold <= max) {
    const y = T + ph - (opts.threshold / max) * ph;
    g.setLineDash([5, 4]); g.strokeStyle = "rgba(248,113,113,.6)"; g.beginPath(); g.moveTo(L, y); g.lineTo(w - R, y); g.stroke(); g.setLineDash([]);
  }
  let any = false;
  series.forEach((s) => {
    g.strokeStyle = s.color; g.fillStyle = s.color; g.lineWidth = 2; g.beginPath(); let started = false;
    s.points.forEach((p) => {
      if (p.v === null) { started = false; return; }
      any = true;
      const x = L + pw - (p.age / win) * pw, y = T + ph - (p.v / max) * ph;
      if (!started) { g.moveTo(x, y); started = true; } else g.lineTo(x, y);
    });
    g.stroke();
    s.points.forEach((p) => { if (p.v !== null) { const x = L + pw - (p.age / win) * pw, y = T + ph - (p.v / max) * ph; g.beginPath(); g.arc(x, y, 3, 0, 7); g.fill(); } });
  });
  if (!any) { g.fillStyle = "#9a95b8"; g.textAlign = "center"; g.fillText(opts.empty || "Waiting for measurements...", w / 2, h / 2); g.textAlign = "left"; }
}

/* ---------- status ---------- */
function applyStatus(s) {
  failures = 0; $("banner").classList.add("hidden");
  const sb = $("statusBox"); sb.dataset.state = s.network_status.toLowerCase(); $("statusText").textContent = s.network_status;
  const net = s.internet, gw = s.gateway, dns = s.dns;
  const nc = net.status === "ONLINE" ? "ok" : net.status === "OFFLINE" ? "bad" : "unk";
  setState("internetState", net.status === "UNKNOWN" ? "CHECKING" : net.status, nc); setCard("cardInternet", nc === "unk" ? "" : nc);
  $("internetSub").textContent = net.status === "OFFLINE" ? (net.error || "No response") : "Latency: " + fmt(net.latency_ms, "ms") + (net.http_ms ? "  |  HTTP " + net.http_ms + " ms" : "");
  const gc = gw.status === "REACHABLE" ? "ok" : gw.status === "UNREACHABLE" ? "bad" : "unk";
  setState("gatewayState", gw.status === "UNKNOWN" ? "CHECKING" : gw.status, gc); setCard("cardGateway", gc === "unk" ? "" : gc);
  $("gatewaySub").textContent = (gw.ip ? gw.ip + (gw.source === "manual" ? " (manual)" : "") + "  |  " : "") + (gw.status === "REACHABLE" ? "Latency: " + fmt(gw.latency_ms, "ms") : gw.error || "");
  const dc = dns.status === "AVAILABLE" ? "ok" : dns.status === "FAILED" ? "bad" : "unk";
  setState("dnsState", dns.status === "UNKNOWN" ? "CHECKING" : dns.status, dc); setCard("cardDns", dc === "unk" ? "" : dc);
  $("dnsSub").textContent = dns.status === "AVAILABLE" ? dns.domain + " -> " + dns.ip + "  |  " + dns.response_ms + " ms" : (dns.domain ? dns.domain + ": " : "") + (dns.error || "");
  const loss = net.loss_pct, th = s.thresholds.loss_pct;
  const lc = loss === null ? "unk" : loss > th ? "bad" : loss > 0 ? "warn" : "ok";
  setState("lossValue", loss === null ? "Unavailable" : loss + "%", lc); setCard("cardLoss", lc === "unk" ? "" : lc);
  $("lossSub").textContent = "to " + (net.target || "-") + " (" + (net.method || "-") + ")";
  const bw = s.bandwidth, si = s.selected_interface;
  $("ifaceName").textContent = s.interface || "Unavailable";
  $("ifaceSub").textContent = si ? "Status: " + si.status : (s.interfaces_error || "No active interface");
  $("localIp").textContent = s.local_ip || "Unavailable";
  $("downRate").textContent = bw.down_mbps === null ? "Unavailable" : "\u2193 " + bw.down_mbps.toFixed(2) + " Mbps";
  $("upRate").textContent = bw.up_mbps === null ? "Unavailable" : "\u2191 " + bw.up_mbps.toFixed(2) + " Mbps";
  // health
  const hl = $("healthList"); hl.replaceChildren();
  s.checks.forEach((c) => {
    const li = el("li"); li.append(el("span", "", c.name));
    const mark = c.level === "ok" ? ["\u2713", "ok"] : c.level === "fail" ? ["\u2715", "bad"] : ["-", "unk"];
    li.append(el("span", mark[1], mark[0] + (c.level === "unknown" ? " n/a" : ""))); hl.append(li);
  });
  $("healthReasons").textContent = s.reasons.length ? "Reasons: " + s.reasons.join(" ") : "";
  // alerts
  const al = $("alertList"); al.replaceChildren();
  if (!s.alerts.length) al.append(el("li", "", "No active alerts."));
  s.alerts.forEach((a) => al.append(el("li", a.level, (a.level === "error" ? "\u2715 " : "\u26A0 ") + a.message)));
  // services + urls
  const sl = $("serviceList"); sl.replaceChildren();
  if (!s.services.length) sl.append(el("p", "note", "No services configured. Add one in Configuration."));
  s.services.forEach((v) => sl.append(svcRow(v.name, v.host + ":" + v.port, v.status, v.status === "UP" ? fmt(v.response_ms, "ms") : v.error)));
  const ul = $("urlList"); ul.replaceChildren();
  if (!s.urls.length) ul.append(el("p", "note", "No URLs configured."));
  s.urls.forEach((v) => ul.append(svcRow(v.name, v.url, v.status, (v.status_code ? "HTTP " + v.status_code + "  " : "") + (v.response_ms ? v.response_ms + " ms" : v.error || ""))));
  // interface stats
  const st = $("ifaceStats"); st.replaceChildren();
  if (si) {
    [["Interface", si.name], ["Status", si.status], ["Received", bytes(si.bytes_recv)], ["Sent", bytes(si.bytes_sent)],
     ["Packets received", si.packets_recv === null ? "Unavailable" : si.packets_recv.toLocaleString()],
     ["Packets sent", si.packets_sent === null ? "Unavailable" : si.packets_sent.toLocaleString()],
     ["Errors in / out", (si.errors_in ?? "Unavailable") + " / " + (si.errors_out ?? "Unavailable")]].forEach(([k, v]) => {
      const d = el("div"); d.append(el("small", "", k), el("span", "", String(v))); st.append(d); });
  } else st.append(el("p", "note", s.interfaces_error || "Interface information unavailable."));
}
function svcRow(name, target, status, extra) {
  const r = el("div", "svc"); const l = el("div"); l.append(el("b", "", name), el("small", "", target));
  const right = el("div"); right.style.textAlign = "right";
  const cls = status === "UP" ? "ok" : status === "DOWN" ? "bad" : "unk";
  right.append(el("span", "pill " + cls, status), el("small", "", extra || ""));
  r.append(l, right); return r;
}

async function refreshStatus() {
  try { applyStatus(await api("/api/status")); }
  catch (e) { failures++; if (failures >= 2) { const b = $("banner"); b.textContent = "Cannot reach the NetWatch server. Is it still running?"; b.classList.remove("hidden"); } }
}
async function refreshHistory() {
  try {
    const w = $("windowSelect").value; const h = await api("/api/latency?window=" + w); const win = h.window_s;
    drawChart($("latencyChart"), [{ color: LAV, points: h.ping.map((p) => ({ age: p.age, v: p.latency })) }],
      { window: win, threshold: lastThresholdLat, minMax: 20, empty: "Waiting for ping results..." });
    drawChart($("lossChart"), [{ color: GOLD, points: h.ping.map((p) => ({ age: p.age, v: p.loss })) }], { window: win, minMax: 10, empty: "Waiting for ping results..." });
    drawChart($("bwChart"), [{ color: OK, points: h.bandwidth.map((p) => ({ age: p.age, v: p.down })) }, { color: GOLD, points: h.bandwidth.map((p) => ({ age: p.age, v: p.up })) }],
      { window: win, minMax: 0.5, empty: "Waiting for bandwidth samples..." });
    const s = h.stats, box = $("latStats"); box.replaceChildren();
    [["Current", s.current, "ms"], ["Average", s.avg, "ms"], ["Minimum", s.min, "ms"], ["Maximum", s.max, "ms"], ["Avg loss", s.loss_avg, "%"]].forEach(([k, v, u]) => {
      const d = el("div", "stat"); d.append(el("b", "", v === null ? "Unavailable" : v + " " + u), el("span", "", k)); box.append(d); });
  } catch (e) { /* shown by status banner */ }
}
let lastThresholdLat = 200;
async function refreshEvents() {
  try {
    const d = await api("/api/events"); const ul = $("eventList"); ul.replaceChildren();
    if (!d.events.length) ul.append(el("li", "info", "No events."));
    d.events.forEach((e) => { const li = el("li", e.level); li.append(el("span", "t", e.time), document.createTextNode(e.message)); ul.append(li); });
  } catch (e) { }
}
async function refreshInterfaces() {
  try {
    const d = await api("/api/interfaces"); const sel = $("ifaceSelect");
    if (document.activeElement === sel) return;
    sel.replaceChildren(); const auto = el("option", "", "Auto (" + (d.selected || "none") + ")"); auto.value = "auto"; sel.append(auto);
    d.interfaces.forEach((i) => { const o = el("option", "", i.name + " (" + i.status + (i.ipv4 ? ", " + i.ipv4 : "") + ")"); o.value = i.name; sel.append(o); });
    const cfg = await api("/api/config"); sel.value = cfg.settings.interface; lastThresholdLat = cfg.settings.latency_threshold_ms;
  } catch (e) { }
}
$("ifaceSelect").addEventListener("change", async (ev) => {
  try { await api("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ interface: ev.target.value }) }); refreshStatus(); } catch (e) { alert(e.message); }
});
$("windowSelect").addEventListener("change", refreshHistory);
$("clearLogs").addEventListener("click", async () => { await api("/api/events", { method: "DELETE" }); refreshEvents(); });

/* ---------- troubleshooter ---------- */
$("runDiag").addEventListener("click", async () => {
  const btn = $("runDiag"), box = $("diagResult"); btn.disabled = true; btn.textContent = "Running...";
  box.replaceChildren(el("p", "muted", "Running safe tests, this can take up to about 30 seconds..."));
  try {
    const d = await api("/api/diagnostics"); box.replaceChildren();
    d.steps.forEach((s) => {
      const cls = s.status === "PASS" ? "ok" : s.status === "FAIL" ? "bad" : "unk";
      const row = el("div", "step"); const body = el("div");
      body.append(el("b", "", s.name), el("p", "", s.detail));
      if (s.possible_cause) body.append(el("p", "", "Possible cause: " + s.possible_cause));
      if (s.suggestions.length) body.append(el("p", "", "Suggested troubleshooting step: " + s.suggestions.join("; ")));
      row.append(el("span", "pill " + cls, s.status), body); box.append(row);
    });
    box.append(el("div", "overall", "DIAGNOSTIC RESULT (" + d.time + "): " + d.overall));
  } catch (e) { box.replaceChildren(el("p", "bad", "Diagnostics failed: " + e.message)); }
  btn.disabled = false; btn.textContent = "Run Network Diagnostics";
});

/* ---------- info ---------- */
async function loadInfo() {
  try {
    const d = await api("/api/network-info"); const b = $("infoBox"); b.replaceChildren();
    [["Hostname", d.hostname], ["Operating system", d.os], ["Local IPv4", d.local_ipv4], ["IPv6", d.ipv6.length ? d.ipv6.join(", ") : null],
     ["Default gateway", d.gateway ? d.gateway + " (" + d.gateway_source + ")" : null], ["Selected interface", d.selected_interface], ["MAC address", d.mac],
     ["DNS test domain", d.dns_test_domain], ["Python", d.python]].forEach(([k, v]) => { const x = el("div"); x.append(el("small", "", k), el("span", "", v || "Unavailable")); b.append(x); });
    const tb = document.querySelector("#infoIfaces tbody"); tb.replaceChildren();
    d.interfaces.forEach((i) => { const tr = el("tr"); [i.name, i.status, i.ipv4 || "-", i.mac || "-"].forEach((v) => tr.append(el("td", "", v))); tb.append(tr); });
    $("infoNote").textContent = d.note;
  } catch (e) { $("infoBox").textContent = e.message; }
}

/* ---------- configuration ---------- */
function addRow(container, kind, v) {
  const row = el("div", "row" + (kind === "url" ? " url" : ""));
  const mk = (ph, val, cls, type) => { const i = el("input"); i.placeholder = ph; i.value = val ?? ""; i.className = cls; if (type) i.type = type; return i; };
  if (kind === "svc") row.append(mk("Name", v.name, "n"), mk("Host / IP", v.host, "h"), mk("Port", v.port, "p", "number"));
  else row.append(mk("Name", v.name, "n"), mk("https://...", v.url, "u"));
  const rm = el("button", "btn ghost small", "Remove"); rm.type = "button"; rm.onclick = () => row.remove(); row.append(rm);
  container.append(row);
}
async function loadConfig() {
  try {
    const d = await api("/api/config"), s = d.settings;
    $("cfgGatewayMode").value = s.gateway_mode; $("cfgGatewayIp").value = s.gateway_ip; $("cfgDns").value = s.dns_domain;
    $("cfgPingHost").value = s.internet_ping_host; $("cfgHttp").value = s.internet_http_url; $("cfgLat").value = s.latency_threshold_ms; $("cfgLoss").value = s.packet_loss_threshold_pct;
    $("svcRows").replaceChildren(); s.services.forEach((v) => addRow($("svcRows"), "svc", v));
    $("urlRows").replaceChildren(); s.urls.forEach((v) => addRow($("urlRows"), "url", v));
  } catch (e) { showMsg(e.message, true); }
}
function showMsg(text, isErr) { const m = $("configMsg"); m.textContent = text; m.className = "msg " + (isErr ? "err" : "good"); }
$("addSvc").onclick = () => addRow($("svcRows"), "svc", { name: "", host: "", port: "" });
$("addUrl").onclick = () => addRow($("urlRows"), "url", { name: "", url: "https://" });
$("configForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const body = {
    gateway_mode: $("cfgGatewayMode").value, gateway_ip: $("cfgGatewayIp").value, dns_domain: $("cfgDns").value,
    internet_ping_host: $("cfgPingHost").value, internet_http_url: $("cfgHttp").value,
    latency_threshold_ms: $("cfgLat").value, packet_loss_threshold_pct: $("cfgLoss").value,
    services: [...$("svcRows").children].map((r) => ({ name: r.querySelector(".n").value, host: r.querySelector(".h").value, port: r.querySelector(".p").value })),
    urls: [...$("urlRows").children].map((r) => ({ name: r.querySelector(".n").value, url: r.querySelector(".u").value })),
  };
  try {
    await api("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    showMsg("Settings saved. New checks start on the next cycle.", false); lastThresholdLat = +body.latency_threshold_ms;
  } catch (e) { showMsg((e.message || "Invalid") + (e.details ? ": " + e.details.join(" ") : ""), true); }
});

/* ---------- schedule: fast metrics 2 s, history 4 s, events 4 s ---------- */
refreshStatus(); refreshInterfaces(); refreshHistory(); refreshEvents();
setInterval(refreshStatus, 2000);
setInterval(() => { refreshHistory(); refreshEvents(); }, 4000);
setInterval(refreshInterfaces, 15000);
window.addEventListener("resize", refreshHistory);
