/**
 * JARVIS Live Lab — watch JARVIS work in real time.
 *
 * Renders a right-side panel with two halves:
 *   1. Activity stream — every step JARVIS takes (search, read, note, write)
 *   2. Live document — markdown that grows word-by-word as JARVIS writes
 *
 * Driven by `{"type": "live_lab", ...}` WebSocket events.
 */

type StepKind = "search" | "read" | "note" | "plan" | "write" | "render";

interface LiveLabMessage {
  type: "live_lab";
  id: string;
  event:
    | "session_start"
    | "step"
    | "doc_chunk"
    | "doc_replace"
    | "session_end"
    | "session_error";
  topic?: string;
  kind?: StepKind;
  text?: string;
  success?: boolean;
  path?: string;
  error?: string;
}

let panelEl: HTMLElement | null = null;
let activityEl: HTMLElement | null = null;
let docEl: HTMLElement | null = null;
let headerEl: HTMLElement | null = null;
let isOpen = false;

const KIND_LABELS: Record<StepKind, { icon: string; color: string }> = {
  search: { icon: "🔍", color: "#3b82f6" },
  read:   { icon: "📖", color: "#06b6d4" },
  note:   { icon: "📝", color: "#10b981" },
  plan:   { icon: "🗂️",  color: "#a855f7" },
  write:  { icon: "✍️",  color: "#f59e0b" },
  render: { icon: "📄", color: "#94a3b8" },
};

// ---------------------------------------------------------------------------
// DOM scaffold (lazy-built on first event)
// ---------------------------------------------------------------------------

function buildPanel(): void {
  if (panelEl) return;

  panelEl = document.createElement("div");
  panelEl.id = "live-lab";
  panelEl.innerHTML = `
    <div id="live-lab-header">
      <span id="live-lab-title">Live Lab</span>
      <button id="live-lab-close" title="Close">×</button>
    </div>
    <div id="live-lab-activity"></div>
    <div id="live-lab-doc"></div>
  `;
  document.body.appendChild(panelEl);

  const style = document.createElement("style");
  style.textContent = `
    #live-lab {
      position: fixed;
      top: 0;
      right: 0;
      width: min(48vw, 720px);
      height: 100vh;
      background: rgba(8, 12, 20, 0.94);
      border-left: 1px solid rgba(56, 189, 248, 0.25);
      backdrop-filter: blur(12px);
      display: flex;
      flex-direction: column;
      z-index: 100;
      box-shadow: -8px 0 32px rgba(0,0,0,0.4);
      transform: translateX(100%);
      transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: #cfd8dc;
    }
    #live-lab.open { transform: translateX(0); }

    #live-lab-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 18px;
      border-bottom: 1px solid rgba(56, 189, 248, 0.15);
      font-size: 0.85rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: #38bdf8;
    }
    #live-lab-close {
      background: transparent;
      border: none;
      color: #64748b;
      font-size: 1.6rem;
      cursor: pointer;
      line-height: 1;
      padding: 0 4px;
    }
    #live-lab-close:hover { color: #cfd8dc; }

    #live-lab-activity {
      flex: 0 0 auto;
      max-height: 38%;
      overflow-y: auto;
      padding: 10px 18px;
      font-size: 0.8rem;
      font-family: 'SF Mono', Menlo, Consolas, monospace;
      border-bottom: 1px solid rgba(56, 189, 248, 0.1);
    }
    .live-step {
      display: flex;
      gap: 10px;
      padding: 5px 0;
      align-items: baseline;
      opacity: 0;
      animation: fadein 0.3s ease forwards;
    }
    @keyframes fadein {
      from { opacity: 0; transform: translateY(4px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .live-step .time {
      color: #475569;
      font-size: 0.7rem;
      flex: 0 0 56px;
    }
    .live-step .icon { font-size: 0.85rem; flex: 0 0 18px; text-align: center; }
    .live-step .text { color: #cbd5e1; flex: 1; word-break: break-word; }

    #live-lab-doc {
      flex: 1 1 auto;
      overflow-y: auto;
      padding: 22px 28px;
      font-size: 0.92rem;
      line-height: 1.65;
      color: #e2e8f0;
      white-space: pre-wrap;
      font-family: -apple-system, 'Segoe UI', sans-serif;
    }
    #live-lab-doc h1 { color: #f1f5f9; font-size: 1.4rem; margin: 0 0 16px; }
    #live-lab-doc h2 { color: #94a3b8; font-size: 1.05rem; margin: 18px 0 8px; letter-spacing: 0.03em; }
    #live-lab-doc a  { color: #38bdf8; }
  `;
  document.head.appendChild(style);

  activityEl = document.getElementById("live-lab-activity");
  docEl = document.getElementById("live-lab-doc");
  headerEl = document.getElementById("live-lab-title");

  document.getElementById("live-lab-close")?.addEventListener("click", () => {
    closePanel();
  });
}

function openPanel(): void {
  buildPanel();
  if (panelEl && !isOpen) {
    requestAnimationFrame(() => panelEl?.classList.add("open"));
    isOpen = true;
  }
}

function closePanel(): void {
  if (panelEl && isOpen) {
    panelEl.classList.remove("open");
    isOpen = false;
  }
}

function timestamp(): string {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}

// ---------------------------------------------------------------------------
// Event handler — call from WebSocket message dispatcher
// ---------------------------------------------------------------------------

export function handleLiveLab(msg: LiveLabMessage): void {
  buildPanel();

  switch (msg.event) {
    case "session_start": {
      if (activityEl) activityEl.innerHTML = "";
      if (docEl) docEl.textContent = "";
      if (headerEl) headerEl.textContent = `Live Lab — ${msg.topic ?? ""}`;
      openPanel();
      break;
    }
    case "step": {
      if (!activityEl) break;
      const kind = (msg.kind ?? "note") as StepKind;
      const meta = KIND_LABELS[kind] ?? KIND_LABELS.note;
      const row = document.createElement("div");
      row.className = "live-step";
      row.innerHTML = `
        <span class="time">${timestamp()}</span>
        <span class="icon" style="color:${meta.color}">${meta.icon}</span>
        <span class="text"></span>
      `;
      row.querySelector(".text")!.textContent = msg.text ?? "";
      activityEl.appendChild(row);
      activityEl.scrollTop = activityEl.scrollHeight;
      break;
    }
    case "doc_chunk": {
      if (!docEl) break;
      // Append as a text node so we never inject HTML
      docEl.appendChild(document.createTextNode(msg.text ?? ""));
      // Auto-scroll if user is near the bottom
      const nearBottom = docEl.scrollHeight - docEl.scrollTop - docEl.clientHeight < 200;
      if (nearBottom) docEl.scrollTop = docEl.scrollHeight;
      break;
    }
    case "doc_replace": {
      if (docEl) docEl.textContent = msg.text ?? "";
      break;
    }
    case "session_end": {
      if (!activityEl) break;
      const row = document.createElement("div");
      row.className = "live-step";
      row.innerHTML = `
        <span class="time">${timestamp()}</span>
        <span class="icon" style="color:#22c55e">✓</span>
        <span class="text"></span>
      `;
      row.querySelector(".text")!.textContent = msg.success
        ? `Saved: ${msg.path ?? "(in-memory)"}`
        : "Session ended.";
      activityEl.appendChild(row);
      activityEl.scrollTop = activityEl.scrollHeight;
      break;
    }
    case "session_error": {
      if (!activityEl) break;
      const row = document.createElement("div");
      row.className = "live-step";
      row.innerHTML = `
        <span class="time">${timestamp()}</span>
        <span class="icon" style="color:#ef4444">!</span>
        <span class="text"></span>
      `;
      row.querySelector(".text")!.textContent = `Error: ${msg.error ?? "unknown"}`;
      activityEl.appendChild(row);
      activityEl.scrollTop = activityEl.scrollHeight;
      break;
    }
  }
}
