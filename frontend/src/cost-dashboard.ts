/**
 * JARVIS Cost Dashboard.
 *
 * Right-side panel that visualizes spend across time periods, features,
 * and providers. Auto-refreshes every 10s while open. Pulls from
 * /api/usage/detailed.
 */

interface DetailedUsage {
  today: PeriodTotals;
  week: PeriodTotals;
  month: PeriodTotals;
  all_time: PeriodTotals;
  session: { cost_usd: number; api_calls: number; tts_calls: number; uptime_seconds: number };
  week_by_day: { date: string; cost_usd: number }[];
  today_by_feature: Record<string, number>;
  today_by_provider: Record<string, number>;
  recent_calls: {
    ts: number;
    feature: string;
    model: string;
    provider: string;
    in: number;
    out: number;
    chars: number;
    cost_usd: number;
  }[];
}
interface PeriodTotals {
  cost_usd: number;
  calls: number;
  in_tokens: number;
  out_tokens: number;
  tts_chars: number;
  label?: string;
}

const FEATURE_COLORS: Record<string, string> = {
  chat:                  "#38bdf8",
  classify:              "#a855f7",
  live_research:         "#f59e0b",
  research_opus:         "#ef4444",
  research_summary:      "#fb923c",
  screen_vision_hotkey:  "#10b981",
  screen_vision_voice:   "#06b6d4",
  screen_vision_auto:    "#0ea5e9",
  screen_summary:        "#14b8a6",
  summary:               "#fbbf24",
  dispatch_summary:      "#facc15",
  work_summary:          "#fde047",
  build_summary:         "#eab308",
  session_summary:       "#84cc16",
  tts:                   "#ec4899",
  tts_proactive:         "#f472b6",
  other:                 "#94a3b8",
};
const PROVIDER_COLORS: Record<string, string> = {
  anthropic: "#d97706",
  ollama:    "#22c55e",
  openai:    "#0ea5e9",
};

let panelEl: HTMLElement | null = null;
let bodyEl: HTMLElement | null = null;
let isOpen = false;
let refreshTimer: number | null = null;

function fmtUSD(n: number): string {
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}
function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toTimeString().slice(0, 8);
}
function shortDate(s: string): string {
  // "2026-05-12" -> "May 12"
  try {
    const [, mm, dd] = s.split("-");
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${months[parseInt(mm, 10) - 1]} ${parseInt(dd, 10)}`;
  } catch { return s; }
}

// ---------------------------------------------------------------------------
// DOM scaffold
// ---------------------------------------------------------------------------

function buildPanel(): void {
  if (panelEl) return;

  panelEl = document.createElement("div");
  panelEl.id = "cost-dashboard";
  panelEl.innerHTML = `
    <div id="cost-header">
      <span id="cost-title">Cost Dashboard</span>
      <div style="display:flex;gap:6px;align-items:center">
        <button id="cost-refresh" title="Refresh">↻</button>
        <button id="cost-close" title="Close">×</button>
      </div>
    </div>
    <div id="cost-body">Loading...</div>
  `;
  document.body.appendChild(panelEl);

  const style = document.createElement("style");
  style.textContent = `
    #cost-dashboard {
      position: fixed; top: 0; right: 0;
      width: min(50vw, 760px); height: 100vh;
      background: rgba(8, 12, 20, 0.96);
      border-left: 1px solid rgba(56,189,248,0.22);
      backdrop-filter: blur(10px);
      z-index: 101;
      display: flex; flex-direction: column;
      transform: translateX(100%);
      transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
      box-shadow: -8px 0 32px rgba(0,0,0,0.4);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: #cfd8dc;
    }
    #cost-dashboard.open { transform: translateX(0); }
    #cost-header {
      display:flex; align-items:center; justify-content:space-between;
      padding: 14px 18px; border-bottom: 1px solid rgba(56,189,248,0.15);
      font-size: 0.85rem; letter-spacing: 0.18em; text-transform: uppercase;
      color: #38bdf8;
    }
    #cost-header button {
      background: transparent; border: none; color: #64748b;
      font-size: 1.2rem; cursor: pointer; padding: 2px 8px;
    }
    #cost-header button:hover { color: #cfd8dc; }
    #cost-close { font-size: 1.6rem !important; line-height: 1; }
    #cost-body { flex: 1; overflow-y: auto; padding: 18px 20px; }
    .cost-kpis { display:grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 18px; }
    .cost-kpi {
      background: rgba(56,189,248,0.06);
      border: 1px solid rgba(56,189,248,0.15);
      border-radius: 6px; padding: 10px 14px;
    }
    .cost-kpi .label { font-size: 0.7rem; color: #64748b; letter-spacing: 0.1em; text-transform: uppercase; }
    .cost-kpi .value { font-size: 1.4rem; color: #e2e8f0; font-weight: 600; margin-top: 2px; }
    .cost-kpi .sub  { font-size: 0.72rem; color: #64748b; margin-top: 2px; }

    .cost-section-title {
      font-size: 0.7rem; letter-spacing: 0.15em; text-transform: uppercase;
      color: #64748b; margin: 18px 0 8px;
    }
    .cost-bar-row {
      display: grid; grid-template-columns: 110px 1fr 70px;
      align-items: center; gap: 10px; padding: 4px 0;
      font-size: 0.82rem;
    }
    .cost-bar-row .name { color: #cbd5e1; }
    .cost-bar-row .bar  {
      height: 10px; border-radius: 3px; background: rgba(255,255,255,0.04);
      overflow: hidden;
    }
    .cost-bar-row .bar > div { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
    .cost-bar-row .val  { font-family: 'SF Mono', Menlo, Consolas, monospace; color: #94a3b8; text-align: right; font-size: 0.78rem; }

    .cost-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 18px; }

    .cost-recent {
      margin-top: 22px;
      font-size: 0.74rem;
      font-family: 'SF Mono', Menlo, Consolas, monospace;
    }
    .cost-recent .row {
      display: grid;
      grid-template-columns: 60px 1fr 1fr 60px;
      gap: 8px;
      padding: 3px 0;
      border-bottom: 1px solid rgba(56,189,248,0.05);
    }
    .cost-recent .row .ts { color: #475569; }
    .cost-recent .row .feature { color: #cbd5e1; }
    .cost-recent .row .model   { color: #64748b; }
    .cost-recent .row .cost    { color: #94a3b8; text-align: right; }
  `;
  document.head.appendChild(style);

  bodyEl = document.getElementById("cost-body");
  document.getElementById("cost-close")?.addEventListener("click", () => closePanel());
  document.getElementById("cost-refresh")?.addEventListener("click", () => refresh());
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderBarRow(name: string, value: number, max: number, color: string): string {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  const safeName = name.replace(/</g, "&lt;");
  return `
    <div class="cost-bar-row">
      <span class="name">${safeName}</span>
      <span class="bar"><div style="width:${pct}%;background:${color}"></div></span>
      <span class="val">${fmtUSD(value)}</span>
    </div>
  `;
}

function render(data: DetailedUsage): void {
  if (!bodyEl) return;

  // KPIs
  const kpis = `
    <div class="cost-kpis">
      <div class="cost-kpi">
        <div class="label">Today</div>
        <div class="value">${fmtUSD(data.today.cost_usd)}</div>
        <div class="sub">${data.today.calls} calls</div>
      </div>
      <div class="cost-kpi">
        <div class="label">This Week</div>
        <div class="value">${fmtUSD(data.week.cost_usd)}</div>
        <div class="sub">${data.week.calls} calls</div>
      </div>
      <div class="cost-kpi">
        <div class="label">This Month</div>
        <div class="value">${fmtUSD(data.month.cost_usd)}</div>
        <div class="sub">${data.month.calls} calls</div>
      </div>
      <div class="cost-kpi">
        <div class="label">All Time</div>
        <div class="value">${fmtUSD(data.all_time.cost_usd)}</div>
        <div class="sub">${data.all_time.calls} calls</div>
      </div>
    </div>
  `;

  // 7-day bars
  const weekMax = Math.max(0.001, ...data.week_by_day.map(d => d.cost_usd));
  const week = data.week_by_day.map(d =>
    renderBarRow(shortDate(d.date), d.cost_usd, weekMax, "#38bdf8")
  ).join("") || `<div style="font-size:0.78rem;color:#64748b;padding:6px 0">No spend in the last 7 days.</div>`;

  // Today by feature
  const featEntries = Object.entries(data.today_by_feature || {});
  const featMax = Math.max(0.001, ...featEntries.map(([, v]) => v));
  const features = featEntries.length
    ? featEntries.map(([k, v]) => renderBarRow(k, v, featMax, FEATURE_COLORS[k] || FEATURE_COLORS.other)).join("")
    : `<div style="font-size:0.78rem;color:#64748b">No spend today yet.</div>`;

  // Today by provider
  const provEntries = Object.entries(data.today_by_provider || {});
  const provMax = Math.max(0.001, ...provEntries.map(([, v]) => v));
  const providers = provEntries.length
    ? provEntries.map(([k, v]) => renderBarRow(k, v, provMax, PROVIDER_COLORS[k] || "#94a3b8")).join("")
    : `<div style="font-size:0.78rem;color:#64748b">No spend today yet.</div>`;

  // Recent calls
  const recent = (data.recent_calls || []).map(c => {
    const model = (c.model || "").replace(/^ollama:/, "🟢 ").slice(0, 32);
    return `
      <div class="row">
        <span class="ts">${fmtTime(c.ts)}</span>
        <span class="feature">${c.feature}</span>
        <span class="model">${model}</span>
        <span class="cost">${fmtUSD(c.cost_usd)}</span>
      </div>
    `;
  }).join("") || `<div style="font-size:0.78rem;color:#64748b">No recent calls.</div>`;

  bodyEl.innerHTML = `
    ${kpis}
    <div class="cost-section-title">Last 7 days</div>
    ${week}

    <div class="cost-grid-2">
      <div>
        <div class="cost-section-title">Today by feature</div>
        ${features}
      </div>
      <div>
        <div class="cost-section-title">Today by provider</div>
        ${providers}
      </div>
    </div>

    <div class="cost-section-title" style="margin-top:24px">Recent calls</div>
    <div class="cost-recent">${recent}</div>
  `;
}

async function refresh(): Promise<void> {
  if (!bodyEl) return;
  try {
    const res = await fetch("/api/usage/detailed");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as DetailedUsage;
    if ((data as any).error) {
      bodyEl.textContent = `Error: ${(data as any).error}`;
      return;
    }
    render(data);
  } catch (e) {
    bodyEl.innerHTML = `<div style="color:#ef4444;font-size:0.85rem">Failed to load usage: ${e}</div>`;
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function openCostDashboard(): void {
  buildPanel();
  if (panelEl && !isOpen) {
    requestAnimationFrame(() => panelEl?.classList.add("open"));
    isOpen = true;
    refresh();
    // Auto-refresh every 10s while open
    refreshTimer = window.setInterval(refresh, 10_000);
  } else if (isOpen) {
    refresh();
  }
}

export function closePanel(): void {
  if (panelEl && isOpen) {
    panelEl.classList.remove("open");
    isOpen = false;
    if (refreshTimer != null) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }
}
