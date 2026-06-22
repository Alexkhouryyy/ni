/**
 * JARVIS — Settings Panel
 *
 * Overlay panel for API keys, connection status, preferences, and system info.
 * Slides in from the right with glass-morphism styling.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StatusResponse {
  claude_code_installed: boolean;
  calendar_accessible: boolean;
  mail_accessible: boolean;
  notes_accessible: boolean;
  memory_count: number;
  task_count: number;
  server_port: number;
  uptime_seconds: number;
  env_keys_set: {
    anthropic: boolean;
    openai: boolean;
    openai_tts_voice: string;
    user_name: string;
  };
}

interface PreferencesResponse {
  user_name: string;
  honorific: string;
  calendar_accounts: string;
  study_mode: boolean;
  brutal_honesty_mode: boolean;
  hyper_mode: boolean;
  screen_hotkey_enabled: boolean;
  screen_hotkey: string;
  proactive_enabled: boolean;
  model_fast: string;
  model_smart: string;
  memory_distill_enabled: boolean;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let panelEl: HTMLElement | null = null;
let isOpen = false;
let isFirstTimeSetup = false;
let setupStep = 0; // 0=anthropic, 1=openai, 2=name, 3=done

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url);
  return res.json();
}

async function apiPost<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Panel HTML
// ---------------------------------------------------------------------------

function buildPanelHTML(): string {
  return `
    <div class="settings-backdrop" id="settings-backdrop"></div>
    <div class="settings-panel" id="settings-panel-inner">
      <div class="settings-header">
        <h2>Settings</h2>
        <button class="settings-close" id="settings-close">&times;</button>
      </div>

      <div class="settings-welcome" id="settings-welcome" style="display:none">
        <p>Welcome to JARVIS. Let's get you set up.</p>
      </div>

      <div class="settings-body">

        <!-- API Keys -->
        <section class="settings-section" id="section-api-keys">
          <h3>API Keys</h3>

          <div class="settings-field">
            <label>Anthropic API Key</label>
            <div class="settings-input-row">
              <input type="password" id="input-anthropic-key" placeholder="sk-ant-..." />
              <button class="settings-btn" id="btn-test-anthropic">Test</button>
              <span class="status-dot" id="status-anthropic"></span>
            </div>
          </div>

          <div class="settings-field">
            <label>OpenAI API Key</label>
            <div class="settings-input-row">
              <input type="password" id="input-openai-key" placeholder="sk-..." />
              <button class="settings-btn" id="btn-test-openai">Test</button>
              <span class="status-dot" id="status-openai"></span>
            </div>
          </div>

          <div class="settings-field">
            <label>TTS Voice</label>
            <div class="settings-input-row">
              <select id="input-openai-voice">
                <option value="onyx">onyx (deep, JARVIS-like)</option>
                <option value="echo">echo</option>
                <option value="fable">fable</option>
                <option value="alloy">alloy</option>
                <option value="nova">nova</option>
                <option value="shimmer">shimmer</option>
              </select>
              <button class="settings-btn" id="btn-save-voice">Save</button>
            </div>
          </div>

          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-keys">Save Keys</button>
          </div>
        </section>

        <!-- Connection Status -->
        <section class="settings-section" id="section-status">
          <h3>Connection Status</h3>
          <div class="status-grid">
            <div class="status-row"><span class="status-dot" id="status-claude-cli"></span><span>Claude Code CLI</span></div>
            <div class="status-row"><span class="status-dot" id="status-calendar"></span><span>Apple Calendar</span></div>
            <div class="status-row"><span class="status-dot" id="status-mail"></span><span>Apple Mail</span></div>
            <div class="status-row"><span class="status-dot" id="status-notes"></span><span>Apple Notes</span></div>
            <div class="status-row"><span class="status-dot" id="status-server"></span><span>Server</span><span class="status-detail" id="status-server-detail"></span></div>
          </div>
        </section>

        <!-- User Preferences -->
        <section class="settings-section" id="section-preferences">
          <h3>User Preferences</h3>

          <div class="settings-field">
            <label>Your Name</label>
            <input type="text" id="input-user-name" placeholder="Your name" />
          </div>

          <div class="settings-field">
            <label>Honorific</label>
            <select id="input-honorific">
              <option value="sir">Sir</option>
              <option value="ma'am">Ma'am</option>
              <option value="none">None</option>
            </select>
          </div>

          <div class="settings-field">
            <label>Calendar Accounts</label>
            <textarea id="input-calendar-accounts" rows="2" placeholder="auto (or comma-separated emails)"></textarea>
          </div>

          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-prefs">Save Preferences</button>
          </div>
        </section>

        <!-- Google -->
        <section class="settings-section" id="section-google">
          <h3>Google Account</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            Connects Google Calendar and Gmail so JARVIS can brief you on your schedule and inbox.
          </p>
          <div class="status-row" style="margin-bottom:12px">
            <span class="status-dot" id="status-google"></span>
            <span id="google-status-label">Checking...</span>
          </div>
          <p id="google-no-creds" style="display:none;font-size:0.75rem;color:#ef5350;margin-bottom:10px;line-height:1.5">
            ⚠️ <strong>credentials.json</strong> not found.<br/>
            <a href="https://console.cloud.google.com/" target="_blank" style="color:#4fc3f7">Open Google Cloud Console</a>
            → Create project → Enable Calendar + Gmail APIs → Create OAuth credentials (Desktop app type) → Download as <code>credentials.json</code> → place it in your JARVIS folder.
          </p>
          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-google-connect" style="display:none">Connect Google</button>
            <button class="settings-btn" id="btn-google-disconnect" style="display:none;border-color:#ef5350;color:#ef5350">Disconnect</button>
          </div>
        </section>

        <!-- Study Mode -->
        <section class="settings-section" id="section-study-mode">
          <h3 style="color:#6366f1">Study Mode</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            JARVIS becomes a Socratic tutor — he won't give direct answers. He'll ask questions back, make you explain concepts, and quiz you. Toggle off for a session summary.
          </p>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="flex:1;font-size:0.85rem;color:#cfd8dc">Enable Study Mode</span>
            <label class="settings-toggle">
              <input type="checkbox" id="toggle-study-mode" />
              <span class="settings-toggle-slider"></span>
            </label>
          </div>
          <p style="font-size:0.72rem;color:#455a64;line-height:1.4;margin:0">
            When active, the orb turns indigo. Toggle off to hear your session summary.
          </p>
        </section>

        <!-- Brutal Honesty Mode -->
        <section class="settings-section" id="section-brutal-mode">
          <h3 style="color:#ef4444">Brutal Honesty Mode</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            JARVIS drops all diplomacy. Zero filter. He'll swear, call out bullshit directly, and refuse to soften bad news. You asked for the truth — he'll deliver it.
          </p>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="flex:1;font-size:0.85rem;color:#cfd8dc">Enable Brutal Honesty Mode</span>
            <label class="settings-toggle">
              <input type="checkbox" id="toggle-brutal-mode" />
              <span class="settings-toggle-slider"></span>
            </label>
          </div>
          <p style="font-size:0.72rem;color:#455a64;line-height:1.4;margin:0">
            When active, the orb turns crimson. Toggle off to return to normal JARVIS.
          </p>
        </section>

        <!-- Hyper Intelligence Mode -->
        <section class="settings-section" id="section-hyper-mode">
          <h3 style="color:#fbbf24">Hyper Intelligence Mode</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            JARVIS runs every request through a full strategic reasoning pipeline — objective, options, prediction, recommendation, next steps. Denser, sharper, decision-grade answers. Auto-creates tasks and notes when the analysis calls for it.
          </p>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="flex:1;font-size:0.85rem;color:#cfd8dc">Enable Hyper Intelligence Mode</span>
            <label class="settings-toggle">
              <input type="checkbox" id="toggle-hyper-mode" />
              <span class="settings-toggle-slider"></span>
            </label>
          </div>
          <p style="font-size:0.72rem;color:#455a64;line-height:1.4;margin:0">
            When active, the orb turns gold. Toggle off to return to normal JARVIS.
          </p>
        </section>

        <!-- Screen Vision Hotkey -->
        <section class="settings-section" id="section-screen-hotkey">
          <h3>Screen Hotkey</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            Press this hotkey anywhere on your OS — VSCode, Chrome, a terminal, a PDF — and JARVIS will glance at your screen and speak a response. No always-on watching; the hotkey press IS the permission.
          </p>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="flex:1;font-size:0.85rem;color:#cfd8dc">Enable screen hotkey</span>
            <label class="settings-toggle">
              <input type="checkbox" id="toggle-screen-hotkey" />
              <span class="settings-toggle-slider"></span>
            </label>
          </div>
          <div style="display:flex;align-items:center;gap:8px;margin-top:8px">
            <input type="text" id="input-screen-hotkey" placeholder="&lt;ctrl&gt;+&lt;shift&gt;+j" style="flex:1;padding:6px 8px;background:#0f1419;border:1px solid #263238;border-radius:4px;color:#cfd8dc;font-family:monospace;font-size:0.8rem" />
            <button type="button" id="btn-record-screen-hotkey" class="settings-btn" style="padding:6px 12px;font-size:0.78rem">Record</button>
          </div>
          <p style="font-size:0.72rem;color:#455a64;line-height:1.4;margin:8px 0 0">
            Syntax: pynput combo format (e.g. <code>&lt;ctrl&gt;+&lt;shift&gt;+j</code>, <code>&lt;cmd&gt;+&lt;alt&gt;+j</code>). On macOS you'll be asked to grant Accessibility permission on first launch.
          </p>
        </section>

        <!-- Model Routing -->
        <section class="settings-section" id="section-model-routing">
          <h3>AI Models</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            Switch JARVIS between Claude (paid) and your local Ollama (free, runs on your GPU). The dropdowns auto-populate based on what's installed.
          </p>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="flex:1;font-size:0.85rem;color:#cfd8dc">Main chat / smart tier</span>
            <select id="select-model-smart" style="flex:1;padding:6px 8px;background:#0f1419;border:1px solid #263238;border-radius:4px;color:#cfd8dc;font-size:0.8rem">
              <option value="claude-haiku-4-5">Loading...</option>
            </select>
          </div>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="flex:1;font-size:0.85rem;color:#cfd8dc">Background / fast tier</span>
            <select id="select-model-fast" style="flex:1;padding:6px 8px;background:#0f1419;border:1px solid #263238;border-radius:4px;color:#cfd8dc;font-size:0.8rem">
              <option value="claude-haiku-4-5">Loading...</option>
            </select>
          </div>
          <p style="font-size:0.72rem;color:#455a64;line-height:1.4;margin:8px 0 0">
            Fast tier handles classification, summaries, and background tasks. Smart tier handles your main conversation. Switching to <code>ollama:*</code> models is free but quality varies — try them.
          </p>
        </section>

        <!-- Memory -->
        <section class="settings-section" id="section-memory">
          <h3>Memory</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            JARVIS learns stable facts about you in the background — preferences, projects, decisions, ongoing commitments. He carries these across sessions. Toggle off during sensitive conversations.
          </p>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
            <span style="flex:1;font-size:0.85rem;color:#cfd8dc">Enable memory consolidation</span>
            <label class="settings-toggle">
              <input type="checkbox" id="toggle-memory-distill" />
              <span class="settings-toggle-slider"></span>
            </label>
          </div>
          <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
            <button id="btn-view-me-md" class="settings-btn" style="padding:6px 12px;font-size:0.78rem">View me.md</button>
            <button id="btn-refresh-me-md" class="settings-btn" style="padding:6px 12px;font-size:0.78rem">Refresh digest</button>
            <button id="btn-forget-all" class="settings-btn" style="padding:6px 12px;font-size:0.78rem;background:#7f1d1d;border-color:#991b1b;color:#fee2e2">Forget everything</button>
          </div>
          <pre id="me-md-display" style="display:none;margin-top:12px;padding:12px;background:#0f1419;border:1px solid #263238;border-radius:4px;color:#cfd8dc;font-size:0.75rem;line-height:1.5;max-height:320px;overflow-y:auto;white-space:pre-wrap;font-family:'SF Mono',Menlo,Consolas,monospace"></pre>
        </section>

        <!-- Floating Orb (Desktop Shell) -->
        <section class="settings-section" id="section-floating-orb">
          <h3>Floating Orb</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            JARVIS as an always-on-top desktop window. Double-click the <strong>JARVIS</strong> icon on your Desktop. The orb sits in a corner of your screen across every app, click to expand, drag to reposition. Press <code>Ctrl+Shift+\</code> to hide / show.
          </p>
          <div style="display:flex;align-items:center;gap:12px;margin:14px 0 8px;padding-top:12px;border-top:1px solid rgba(56,189,248,0.1)">
            <div style="flex:1">
              <div style="font-size:0.85rem;color:#cfd8dc">Launch at Windows sign-in</div>
              <div style="font-size:0.72rem;color:#546e7a;margin-top:2px">Adds a shortcut to your Startup folder. Sign in and JARVIS is already awake.</div>
            </div>
            <label class="settings-toggle">
              <input type="checkbox" id="toggle-auto-launch" />
              <span class="settings-toggle-slider"></span>
            </label>
          </div>
          <p style="font-size:0.72rem;color:#455a64;line-height:1.4;margin:8px 0 0">
            Tray icon (system tray, bottom-right of taskbar): right-click for Show / Hide / Quit.
          </p>
        </section>

        <!-- Proactive Interruptions -->
        <section class="settings-section" id="section-proactive">
          <h3>Proactive Interruptions</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            JARVIS speaks up about meetings, overdue tasks, and weather shifts without being asked. Toggle off during deep focus or meetings — takes effect within 60 seconds, no restart needed.
          </p>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="flex:1;font-size:0.85rem;color:#cfd8dc">Enable proactive interruptions</span>
            <label class="settings-toggle">
              <input type="checkbox" id="toggle-proactive" />
              <span class="settings-toggle-slider"></span>
            </label>
          </div>
        </section>

        <!-- Live Conversation Mode -->
        <section class="settings-section" id="section-live-conversation">
          <h3>Live Conversation Mode</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:12px;line-height:1.5">
            Stream responses sentence by sentence and keep the mic active while JARVIS speaks — so you can interrupt naturally mid-sentence.
          </p>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="flex:1;font-size:0.85rem;color:#cfd8dc">Enable Live Conversation</span>
            <label class="settings-toggle">
              <input type="checkbox" id="toggle-interruptible" />
              <span class="settings-toggle-slider"></span>
            </label>
          </div>
          <p style="font-size:0.72rem;color:#455a64;line-height:1.4;margin:0">
            Tip: say at least 2 words to interrupt. Works best with headphones to avoid echo.
          </p>
        </section>

        <!-- Personality -->
        <section class="settings-section" id="section-personality">
          <h3>Personality</h3>
          <p style="font-size:0.78rem;color:#546e7a;margin-bottom:10px;line-height:1.5">
            Write how you want JARVIS to sound — tone, phrases, rules. Changes take effect immediately, no restart needed.
          </p>
          <div class="settings-field">
            <textarea id="input-personality" rows="10" placeholder="Loading..."></textarea>
          </div>
          <div class="settings-actions">
            <button class="settings-btn primary" id="btn-save-personality">Save Personality</button>
            <span id="personality-status" style="font-size:0.78rem;color:#4fc3f7;margin-left:10px;opacity:0;transition:opacity 0.3s"></span>
          </div>
        </section>

        <!-- System Info -->
        <section class="settings-section" id="section-sysinfo">
          <h3>System Info</h3>
          <div class="sysinfo-grid">
            <div class="sysinfo-row"><span class="sysinfo-label">Memory entries</span><span id="sysinfo-memory">--</span></div>
            <div class="sysinfo-row"><span class="sysinfo-label">Tasks</span><span id="sysinfo-tasks">--</span></div>
            <div class="sysinfo-row"><span class="sysinfo-label">Server port</span><span id="sysinfo-port">--</span></div>
            <div class="sysinfo-row"><span class="sysinfo-label">Uptime</span><span id="sysinfo-uptime">--</span></div>
          </div>
        </section>

        <!-- Setup Navigation (first-time only) -->
        <div class="setup-nav" id="setup-nav" style="display:none">
          <button class="settings-btn primary" id="btn-setup-next">Next</button>
        </div>

      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Panel lifecycle
// ---------------------------------------------------------------------------

function createPanel(): HTMLElement {
  const container = document.createElement("div");
  container.id = "settings-container";
  container.innerHTML = buildPanelHTML();
  document.body.appendChild(container);
  return container;
}

function setDotStatus(id: string, status: "green" | "red" | "yellow" | "off") {
  const dot = document.getElementById(id);
  if (!dot) return;
  dot.className = "status-dot";
  if (status !== "off") dot.classList.add(`status-${status}`);
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

async function loadStatus() {
  try {
    const status = await apiGet<StatusResponse>("/api/settings/status");

    setDotStatus("status-claude-cli", status.claude_code_installed ? "green" : "red");
    setDotStatus("status-calendar", status.calendar_accessible ? "green" : "red");
    setDotStatus("status-mail", status.mail_accessible ? "green" : "red");
    setDotStatus("status-notes", status.notes_accessible ? "green" : "red");
    setDotStatus("status-server", "green");

    const serverDetail = document.getElementById("status-server-detail");
    if (serverDetail) serverDetail.textContent = `port ${status.server_port} | up ${formatUptime(status.uptime_seconds)}`;

    // API key status dots
    setDotStatus("status-anthropic", status.env_keys_set.anthropic ? "green" : "red");
    setDotStatus("status-openai", status.env_keys_set.openai ? "green" : "red");
    const voiceEl = document.getElementById("input-openai-voice") as HTMLSelectElement;
    if (voiceEl && status.env_keys_set.openai_tts_voice) voiceEl.value = status.env_keys_set.openai_tts_voice;

    // System info
    const memEl = document.getElementById("sysinfo-memory");
    if (memEl) memEl.textContent = String(status.memory_count);
    const taskEl = document.getElementById("sysinfo-tasks");
    if (taskEl) taskEl.textContent = String(status.task_count);
    const portEl = document.getElementById("sysinfo-port");
    if (portEl) portEl.textContent = String(status.server_port);
    const upEl = document.getElementById("sysinfo-uptime");
    if (upEl) upEl.textContent = formatUptime(status.uptime_seconds);

    return status;
  } catch (e) {
    console.error("[settings] failed to load status:", e);
    setDotStatus("status-server", "red");
    return null;
  }
}

async function loadPreferences() {
  try {
    const prefs = await apiGet<PreferencesResponse>("/api/settings/preferences");
    const nameEl = document.getElementById("input-user-name") as HTMLInputElement;
    const honEl = document.getElementById("input-honorific") as HTMLSelectElement;
    const calEl = document.getElementById("input-calendar-accounts") as HTMLTextAreaElement;
    const studyEl = document.getElementById("toggle-study-mode") as HTMLInputElement | null;
    if (nameEl) nameEl.value = prefs.user_name || "";
    if (honEl) honEl.value = prefs.honorific || "sir";
    if (calEl) calEl.value = prefs.calendar_accounts || "auto";
    if (studyEl) {
      studyEl.checked = !!prefs.study_mode;
      (window as any).__jarvis_setStudyMode?.(!!prefs.study_mode);
    }
    const brutalEl = document.getElementById("toggle-brutal-mode") as HTMLInputElement | null;
    if (brutalEl) {
      brutalEl.checked = !!prefs.brutal_honesty_mode;
      (window as any).__jarvis_setBrutalMode?.(!!prefs.brutal_honesty_mode);
    }
    const hyperEl = document.getElementById("toggle-hyper-mode") as HTMLInputElement | null;
    if (hyperEl) {
      hyperEl.checked = !!prefs.hyper_mode;
      (window as any).__jarvis_setHyperMode?.(!!prefs.hyper_mode);
    }
    const hotkeyEnabledEl = document.getElementById("toggle-screen-hotkey") as HTMLInputElement | null;
    if (hotkeyEnabledEl) hotkeyEnabledEl.checked = prefs.screen_hotkey_enabled !== false;
    const hotkeyComboEl = document.getElementById("input-screen-hotkey") as HTMLInputElement | null;
    if (hotkeyComboEl) hotkeyComboEl.value = prefs.screen_hotkey || "<ctrl>+<shift>+j";
    const proactiveEl = document.getElementById("toggle-proactive") as HTMLInputElement | null;
    if (proactiveEl) proactiveEl.checked = prefs.proactive_enabled !== false;
    const memoryEl = document.getElementById("toggle-memory-distill") as HTMLInputElement | null;
    if (memoryEl) memoryEl.checked = prefs.memory_distill_enabled !== false;

    // Auto-launch toggle — separate endpoint (not in main preferences)
    try {
      const status = await apiGet<{ enabled: boolean; supported: boolean }>("/api/startup/status");
      const autoEl = document.getElementById("toggle-auto-launch") as HTMLInputElement | null;
      if (autoEl) {
        autoEl.checked = !!status.enabled;
        autoEl.disabled = !status.supported;
        if (!status.supported) autoEl.title = "Auto-launch is Windows-only for now.";
      }
    } catch (e) {
      console.warn("[settings] auto-launch status failed:", e);
    }

    // Populate model dropdowns from /api/llm/models
    try {
      const models = await apiGet<{ all: string[] }>("/api/llm/models");
      const fastSel = document.getElementById("select-model-fast") as HTMLSelectElement | null;
      const smartSel = document.getElementById("select-model-smart") as HTMLSelectElement | null;
      for (const sel of [fastSel, smartSel]) {
        if (!sel) continue;
        sel.innerHTML = "";
        for (const m of models.all) {
          const opt = document.createElement("option");
          opt.value = m; opt.textContent = m;
          sel.appendChild(opt);
        }
      }
      if (fastSel) fastSel.value = prefs.model_fast || "claude-haiku-4-5";
      if (smartSel) smartSel.value = prefs.model_smart || "claude-haiku-4-5";
    } catch (e) {
      console.error("[settings] failed to load models:", e);
    }
  } catch (e) {
    console.error("[settings] failed to load preferences:", e);
  }
}

async function loadGoogleStatus() {
  try {
    const res = await apiGet<{
      connected: boolean;
      has_credentials: boolean;
      oauth_running?: boolean;
      oauth_error?: string | null;
    }>("/api/google/status");

    const dot        = document.getElementById("status-google");
    const label      = document.getElementById("google-status-label");
    const noCreds    = document.getElementById("google-no-creds");
    const btnConnect = document.getElementById("btn-google-connect") as HTMLButtonElement;
    const btnDisc    = document.getElementById("btn-google-disconnect") as HTMLButtonElement;

    // Reset dot classes first
    if (dot) dot.className = "status-dot";

    if (res.connected) {
      dot?.classList.add("status-green");
      if (label) label.textContent = "Connected";
      if (noCreds) noCreds.style.display = "none";
      if (btnConnect) { btnConnect.style.display = "none"; btnConnect.disabled = false; btnConnect.textContent = "Connect Google"; }
      if (btnDisc) btnDisc.style.display = "inline-block";
    } else if (res.oauth_running) {
      dot?.classList.add("status-yellow");
      if (label) label.textContent = "Authorizing...";
      if (noCreds) noCreds.style.display = "none";
      if (btnConnect) { btnConnect.style.display = "inline-block"; btnConnect.disabled = true; btnConnect.textContent = "Waiting..."; }
      if (btnDisc) btnDisc.style.display = "none";
    } else {
      dot?.classList.add("status-red");
      if (label) label.textContent = res.oauth_error ? `Error: ${res.oauth_error}` : "Not connected";
      if (noCreds) noCreds.style.display = res.has_credentials ? "none" : "block";
      if (btnConnect) { btnConnect.style.display = "inline-block"; btnConnect.disabled = false; btnConnect.textContent = "Connect Google"; }
      if (btnDisc) btnDisc.style.display = "none";
    }
  } catch (e) {
    console.error("[settings] failed to load Google status:", e);
  }
}

async function loadPersonality() {
  try {
    const res = await apiGet<{ content: string }>("/api/settings/personality");
    const el = document.getElementById("input-personality") as HTMLTextAreaElement;
    if (el) el.value = res.content || "";
  } catch (e) {
    console.error("[settings] failed to load personality:", e);
  }
}

function wireEvents() {
  // Close
  document.getElementById("settings-close")?.addEventListener("click", closeSettings);
  document.getElementById("settings-backdrop")?.addEventListener("click", closeSettings);

  // Save keys
  document.getElementById("btn-save-keys")?.addEventListener("click", async () => {
    const anthropicKey = (document.getElementById("input-anthropic-key") as HTMLInputElement).value.trim();
    const openaiKey = (document.getElementById("input-openai-key") as HTMLInputElement).value.trim();

    if (anthropicKey) {
      await apiPost("/api/settings/keys", { key_name: "ANTHROPIC_API_KEY", key_value: anthropicKey });
    }
    if (openaiKey) {
      await apiPost("/api/settings/keys", { key_name: "OPENAI_API_KEY", key_value: openaiKey });
    }
    await loadStatus();
  });

  // Save voice
  document.getElementById("btn-save-voice")?.addEventListener("click", async () => {
    const voice = (document.getElementById("input-openai-voice") as HTMLSelectElement).value;
    if (voice) {
      await apiPost("/api/settings/keys", { key_name: "OPENAI_TTS_VOICE", key_value: voice });
    }
  });

  // Test Anthropic
  document.getElementById("btn-test-anthropic")?.addEventListener("click", async () => {
    setDotStatus("status-anthropic", "yellow");
    const key = (document.getElementById("input-anthropic-key") as HTMLInputElement).value.trim();
    try {
      const result = await apiPost<{ valid: boolean; error?: string }>("/api/settings/test-anthropic", { key_value: key || undefined });
      setDotStatus("status-anthropic", result.valid ? "green" : "red");
    } catch {
      setDotStatus("status-anthropic", "red");
    }
  });

  // Test OpenAI
  document.getElementById("btn-test-openai")?.addEventListener("click", async () => {
    setDotStatus("status-openai", "yellow");
    const key = (document.getElementById("input-openai-key") as HTMLInputElement).value.trim();
    try {
      const result = await apiPost<{ valid: boolean; error?: string }>("/api/settings/test-openai", { key_value: key || undefined });
      setDotStatus("status-openai", result.valid ? "green" : "red");
    } catch {
      setDotStatus("status-openai", "red");
    }
  });

  // Google connect — non-blocking OAuth flow
  document.getElementById("btn-google-connect")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-google-connect") as HTMLButtonElement;
    const label = document.getElementById("google-status-label");
    btn.textContent = "Starting...";
    btn.disabled = true;

    try {
      const result = await apiPost<{ success: boolean; auth_url?: string; error?: string }>("/api/google/connect", {});

      if (!result.success) {
        alert(result.error || "Could not start OAuth flow. Make sure credentials.json is in your JARVIS folder.");
        btn.textContent = "Connect Google";
        btn.disabled = false;
        return;
      }

      // Open auth URL in a new tab (backend also tries webbrowser.open)
      if (result.auth_url) {
        window.open(result.auth_url, "_blank");
      }

      // Show waiting state
      btn.textContent = "Waiting for authorization...";
      if (label) label.textContent = "Authorizing in browser...";

      // Poll /api/google/status until connected or error
      let attempts = 0;
      const maxAttempts = 60; // 2 minutes at 2s intervals
      const poll = setInterval(async () => {
        attempts++;
        try {
          const status = await apiGet<{
            connected: boolean;
            has_credentials: boolean;
            oauth_running: boolean;
            oauth_error: string | null;
          }>("/api/google/status");

          if (status.connected) {
            clearInterval(poll);
            await loadGoogleStatus();
            return;
          }

          if (status.oauth_error) {
            clearInterval(poll);
            alert(`OAuth error: ${status.oauth_error}`);
            btn.textContent = "Connect Google";
            btn.disabled = false;
            if (label) label.textContent = "Not connected";
            return;
          }

          if (!status.oauth_running && attempts > 3) {
            // Flow ended without success or error — likely user closed the tab
            clearInterval(poll);
            btn.textContent = "Connect Google";
            btn.disabled = false;
            if (label) label.textContent = "Not connected";
            return;
          }

          if (attempts >= maxAttempts) {
            clearInterval(poll);
            alert("Authorization timed out. Please try again.");
            btn.textContent = "Connect Google";
            btn.disabled = false;
            if (label) label.textContent = "Not connected";
          }
        } catch {
          // Network hiccup — keep polling
        }
      }, 2000);

    } catch (e) {
      console.error("[google] connect error:", e);
      alert("Failed to reach JARVIS server. Is it running?");
      btn.textContent = "Connect Google";
      btn.disabled = false;
    }
  });

  // Google disconnect
  document.getElementById("btn-google-disconnect")?.addEventListener("click", async () => {
    await apiPost("/api/google/disconnect", {});
    await loadGoogleStatus();
  });

  // Live Conversation Mode toggle
  const liveToggle = document.getElementById("toggle-interruptible") as HTMLInputElement | null;
  if (liveToggle) {
    liveToggle.checked = localStorage.getItem("jarvis_interruptible") === "true";
    liveToggle.addEventListener("change", () => {
      const enabled = liveToggle.checked;
      localStorage.setItem("jarvis_interruptible", enabled ? "true" : "false");
      // Sync the runtime flag in main.ts via window bridge (avoids circular import)
      (window as any).__jarvis_setInterruptibleMode?.(enabled);
    });
  }

  // Save personality
  document.getElementById("btn-save-personality")?.addEventListener("click", async () => {
    const content = (document.getElementById("input-personality") as HTMLTextAreaElement).value;
    const statusEl = document.getElementById("personality-status")!;
    try {
      await apiPost("/api/settings/personality", { content });
      statusEl.textContent = "Saved ✓";
      statusEl.style.opacity = "1";
      setTimeout(() => { statusEl.style.opacity = "0"; }, 2500);
    } catch {
      statusEl.textContent = "Save failed";
      statusEl.style.opacity = "1";
    }
  });

  // Study Mode toggle
  const studyToggle = document.getElementById("toggle-study-mode") as HTMLInputElement | null;
  if (studyToggle) {
    studyToggle.addEventListener("change", async () => {
      const enabled = studyToggle.checked;
      // Notify orb and main state machine immediately
      (window as any).__jarvis_setStudyMode?.(enabled);

      // If disabling, request session summary over WebSocket before saving
      if (!enabled) {
        (window as any).__jarvis_sendStudyEnd?.();
      }

      // Persist to server
      const user_name = (document.getElementById("input-user-name") as HTMLInputElement)?.value.trim() ?? "";
      const honorific = (document.getElementById("input-honorific") as HTMLSelectElement)?.value ?? "sir";
      const calendar_accounts = (document.getElementById("input-calendar-accounts") as HTMLTextAreaElement)?.value.trim() ?? "auto";
      const screen_hotkey_enabled = (document.getElementById("toggle-screen-hotkey") as HTMLInputElement | null)?.checked ?? true;
      const screen_hotkey = (document.getElementById("input-screen-hotkey") as HTMLInputElement | null)?.value.trim() || "<ctrl>+<shift>+j";
      await apiPost("/api/settings/preferences", { user_name, honorific, calendar_accounts, study_mode: enabled, brutal_honesty_mode: (document.getElementById("toggle-brutal-mode") as HTMLInputElement | null)?.checked ?? false, hyper_mode: (document.getElementById("toggle-hyper-mode") as HTMLInputElement | null)?.checked ?? false, screen_hotkey_enabled, screen_hotkey, proactive_enabled: (document.getElementById("toggle-proactive") as HTMLInputElement | null)?.checked ?? true, model_fast: (document.getElementById("select-model-fast") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", model_smart: (document.getElementById("select-model-smart") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", memory_distill_enabled: (document.getElementById("toggle-memory-distill") as HTMLInputElement | null)?.checked ?? true });
    });
  }

  // Brutal Honesty Mode toggle
  const brutalToggle = document.getElementById("toggle-brutal-mode") as HTMLInputElement | null;
  if (brutalToggle) {
    brutalToggle.addEventListener("change", async () => {
      const enabled = brutalToggle.checked;
      (window as any).__jarvis_setBrutalMode?.(enabled);
      const user_name = (document.getElementById("input-user-name") as HTMLInputElement)?.value.trim() ?? "";
      const honorific = (document.getElementById("input-honorific") as HTMLSelectElement)?.value ?? "sir";
      const calendar_accounts = (document.getElementById("input-calendar-accounts") as HTMLTextAreaElement)?.value.trim() ?? "auto";
      const study_mode = (document.getElementById("toggle-study-mode") as HTMLInputElement | null)?.checked ?? false;
      const hyper_mode = (document.getElementById("toggle-hyper-mode") as HTMLInputElement | null)?.checked ?? false;
      const screen_hotkey_enabled = (document.getElementById("toggle-screen-hotkey") as HTMLInputElement | null)?.checked ?? true;
      const screen_hotkey = (document.getElementById("input-screen-hotkey") as HTMLInputElement | null)?.value.trim() || "<ctrl>+<shift>+j";
      await apiPost("/api/settings/preferences", { user_name, honorific, calendar_accounts, study_mode, brutal_honesty_mode: enabled, hyper_mode, screen_hotkey_enabled, screen_hotkey, proactive_enabled: (document.getElementById("toggle-proactive") as HTMLInputElement | null)?.checked ?? true, model_fast: (document.getElementById("select-model-fast") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", model_smart: (document.getElementById("select-model-smart") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", memory_distill_enabled: (document.getElementById("toggle-memory-distill") as HTMLInputElement | null)?.checked ?? true });
    });
  }

  // Hyper Intelligence Mode toggle
  const hyperToggle = document.getElementById("toggle-hyper-mode") as HTMLInputElement | null;
  if (hyperToggle) {
    hyperToggle.addEventListener("change", async () => {
      const enabled = hyperToggle.checked;
      (window as any).__jarvis_setHyperMode?.(enabled);
      const user_name = (document.getElementById("input-user-name") as HTMLInputElement)?.value.trim() ?? "";
      const honorific = (document.getElementById("input-honorific") as HTMLSelectElement)?.value ?? "sir";
      const calendar_accounts = (document.getElementById("input-calendar-accounts") as HTMLTextAreaElement)?.value.trim() ?? "auto";
      const study_mode = (document.getElementById("toggle-study-mode") as HTMLInputElement | null)?.checked ?? false;
      const brutal_honesty_mode = (document.getElementById("toggle-brutal-mode") as HTMLInputElement | null)?.checked ?? false;
      const screen_hotkey_enabled = (document.getElementById("toggle-screen-hotkey") as HTMLInputElement | null)?.checked ?? true;
      const screen_hotkey = (document.getElementById("input-screen-hotkey") as HTMLInputElement | null)?.value.trim() || "<ctrl>+<shift>+j";
      await apiPost("/api/settings/preferences", { user_name, honorific, calendar_accounts, study_mode, brutal_honesty_mode, hyper_mode: enabled, screen_hotkey_enabled, screen_hotkey, proactive_enabled: (document.getElementById("toggle-proactive") as HTMLInputElement | null)?.checked ?? true, model_fast: (document.getElementById("select-model-fast") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", model_smart: (document.getElementById("select-model-smart") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", memory_distill_enabled: (document.getElementById("toggle-memory-distill") as HTMLInputElement | null)?.checked ?? true });
    });
  }

  // Save preferences
  document.getElementById("btn-save-prefs")?.addEventListener("click", async () => {
    const user_name = (document.getElementById("input-user-name") as HTMLInputElement).value.trim();
    const honorific = (document.getElementById("input-honorific") as HTMLSelectElement).value;
    const calendar_accounts = (document.getElementById("input-calendar-accounts") as HTMLTextAreaElement).value.trim();
    const study_mode = (document.getElementById("toggle-study-mode") as HTMLInputElement | null)?.checked ?? false;
    const brutal_honesty_mode = (document.getElementById("toggle-brutal-mode") as HTMLInputElement | null)?.checked ?? false;
    const hyper_mode = (document.getElementById("toggle-hyper-mode") as HTMLInputElement | null)?.checked ?? false;
    const screen_hotkey_enabled = (document.getElementById("toggle-screen-hotkey") as HTMLInputElement | null)?.checked ?? true;
    const screen_hotkey = (document.getElementById("input-screen-hotkey") as HTMLInputElement | null)?.value.trim() || "<ctrl>+<shift>+j";
    await apiPost("/api/settings/preferences", { user_name, honorific, calendar_accounts, study_mode, brutal_honesty_mode, hyper_mode, screen_hotkey_enabled, screen_hotkey, proactive_enabled: (document.getElementById("toggle-proactive") as HTMLInputElement | null)?.checked ?? true, model_fast: (document.getElementById("select-model-fast") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", model_smart: (document.getElementById("select-model-smart") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", memory_distill_enabled: (document.getElementById("toggle-memory-distill") as HTMLInputElement | null)?.checked ?? true });
    await loadStatus();
  });

  // Screen Hotkey — toggle + combo input + record button
  const hotkeyToggle = document.getElementById("toggle-screen-hotkey") as HTMLInputElement | null;
  const hotkeyInput = document.getElementById("input-screen-hotkey") as HTMLInputElement | null;
  const hotkeyRecordBtn = document.getElementById("btn-record-screen-hotkey") as HTMLButtonElement | null;

  async function persistHotkey() {
    const user_name = (document.getElementById("input-user-name") as HTMLInputElement)?.value.trim() ?? "";
    const honorific = (document.getElementById("input-honorific") as HTMLSelectElement)?.value ?? "sir";
    const calendar_accounts = (document.getElementById("input-calendar-accounts") as HTMLTextAreaElement)?.value.trim() ?? "auto";
    const study_mode = (document.getElementById("toggle-study-mode") as HTMLInputElement | null)?.checked ?? false;
    const brutal_honesty_mode = (document.getElementById("toggle-brutal-mode") as HTMLInputElement | null)?.checked ?? false;
    const hyper_mode = (document.getElementById("toggle-hyper-mode") as HTMLInputElement | null)?.checked ?? false;
    const screen_hotkey_enabled = hotkeyToggle?.checked ?? true;
    const screen_hotkey = hotkeyInput?.value.trim() || "<ctrl>+<shift>+j";
    await apiPost("/api/settings/preferences", { user_name, honorific, calendar_accounts, study_mode, brutal_honesty_mode, hyper_mode, screen_hotkey_enabled, screen_hotkey, proactive_enabled: (document.getElementById("toggle-proactive") as HTMLInputElement | null)?.checked ?? true, model_fast: (document.getElementById("select-model-fast") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", model_smart: (document.getElementById("select-model-smart") as HTMLSelectElement | null)?.value || "claude-haiku-4-5", memory_distill_enabled: (document.getElementById("toggle-memory-distill") as HTMLInputElement | null)?.checked ?? true });
  }

  hotkeyToggle?.addEventListener("change", persistHotkey);
  hotkeyInput?.addEventListener("change", persistHotkey);

  // Proactive Interruptions — toggle persists on change
  const proactiveToggle = document.getElementById("toggle-proactive") as HTMLInputElement | null;
  proactiveToggle?.addEventListener("change", persistHotkey);

  // Model dropdowns — persist on change so JARVIS instantly uses the new model
  document.getElementById("select-model-fast")?.addEventListener("change", persistHotkey);
  document.getElementById("select-model-smart")?.addEventListener("change", persistHotkey);

  // Memory: distillation toggle persists on change
  document.getElementById("toggle-memory-distill")?.addEventListener("change", persistHotkey);

  // Auto-launch: separate endpoint, flips the Windows Startup shortcut
  document.getElementById("toggle-auto-launch")?.addEventListener("change", async (e) => {
    const el = e.target as HTMLInputElement;
    const wanted = el.checked;
    try {
      const res = await apiPost<{ success: boolean; error?: string }>("/api/startup", { enabled: wanted });
      if (!res.success) {
        el.checked = !wanted;  // revert
        alert(`Couldn't change auto-launch: ${res.error || "unknown error"}`);
      }
    } catch (err) {
      el.checked = !wanted;
      alert(`Couldn't reach the server: ${err}`);
    }
  });

  // Memory: view me.md
  document.getElementById("btn-view-me-md")?.addEventListener("click", async () => {
    const display = document.getElementById("me-md-display") as HTMLElement | null;
    if (!display) return;
    if (display.style.display === "block") {
      display.style.display = "none";
      return;
    }
    try {
      const res = await apiGet<{ content: string; path: string }>("/api/memory/me");
      display.textContent = res.content || "(empty)";
      display.style.display = "block";
    } catch (e) {
      display.textContent = `Failed to load: ${e}`;
      display.style.display = "block";
    }
  });

  // Memory: force-refresh me.md
  document.getElementById("btn-refresh-me-md")?.addEventListener("click", async (e) => {
    const btn = e.target as HTMLButtonElement;
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Refreshing...";
    try {
      await apiPost("/api/memory/refresh", {});
      btn.textContent = "Refreshed ✓";
    } catch {
      btn.textContent = "Failed";
    } finally {
      setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 2500);
    }
  });

  // Memory: forget everything (with confirmation)
  document.getElementById("btn-forget-all")?.addEventListener("click", async (e) => {
    const btn = e.target as HTMLButtonElement;
    if (!confirm("This will delete ALL stored memories about you. Continue?")) return;
    if (!confirm("Really? This cannot be undone.")) return;
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Forgetting...";
    try {
      const res = await apiPost<{ success: boolean; deleted?: number }>("/api/memory/forget-all", {});
      btn.textContent = res.success ? `Forgot ${res.deleted ?? 0} ✓` : "Failed";
    } catch {
      btn.textContent = "Failed";
    } finally {
      setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 3000);
    }
  });

  if (hotkeyRecordBtn && hotkeyInput) {
    hotkeyRecordBtn.addEventListener("click", () => {
      const original = hotkeyRecordBtn.textContent;
      hotkeyRecordBtn.textContent = "Press keys…";
      hotkeyRecordBtn.disabled = true;

      const onKeyDown = (e: KeyboardEvent) => {
        e.preventDefault();
        e.stopPropagation();
        const parts: string[] = [];
        if (e.ctrlKey) parts.push("<ctrl>");
        if (e.altKey) parts.push("<alt>");
        if (e.shiftKey) parts.push("<shift>");
        if (e.metaKey) parts.push("<cmd>");
        const key = e.key.toLowerCase();
        // Skip pure modifier presses
        if (["control", "shift", "alt", "meta"].includes(key)) return;
        parts.push(key.length === 1 ? key : `<${key}>`);
        hotkeyInput.value = parts.join("+");
        hotkeyRecordBtn.textContent = original || "Record";
        hotkeyRecordBtn.disabled = false;
        window.removeEventListener("keydown", onKeyDown, true);
        persistHotkey();
      };
      window.addEventListener("keydown", onKeyDown, true);
    });
  }

  // Setup next button
  document.getElementById("btn-setup-next")?.addEventListener("click", advanceSetup);
}

// ---------------------------------------------------------------------------
// First-time setup wizard
// ---------------------------------------------------------------------------

function enterSetupMode() {
  isFirstTimeSetup = true;
  setupStep = 0;

  const welcome = document.getElementById("settings-welcome");
  if (welcome) welcome.style.display = "block";

  const nav = document.getElementById("setup-nav");
  if (nav) nav.style.display = "flex";

  // Hide sections except API keys
  showSetupStep(0);
}

function showSetupStep(step: number) {
  const sections = ["section-api-keys", "section-status", "section-preferences", "section-sysinfo"];
  sections.forEach((id, i) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (step === 0 && i === 0) el.style.display = "";
    else if (step === 1 && i === 0) el.style.display = "";
    else if (step === 2 && i === 2) el.style.display = "";
    else if (step === 3) el.style.display = "";
    else el.style.display = "none";
  });

  const nextBtn = document.getElementById("btn-setup-next");
  if (nextBtn) {
    if (step === 0) nextBtn.textContent = "Next: Test Keys";
    else if (step === 1) nextBtn.textContent = "Next: Set Your Name";
    else if (step === 2) nextBtn.textContent = "Finish Setup";
    else nextBtn.style.display = "none";
  }
}

async function advanceSetup() {
  setupStep++;
  if (setupStep >= 3) {
    // Done — save everything and close
    isFirstTimeSetup = false;
    const welcome = document.getElementById("settings-welcome");
    if (welcome) welcome.style.display = "none";
    const nav = document.getElementById("setup-nav");
    if (nav) nav.style.display = "none";

    // Show all sections
    ["section-api-keys", "section-status", "section-preferences", "section-sysinfo"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.style.display = "";
    });

    closeSettings();
    return;
  }
  showSetupStep(setupStep);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function openSettings() {
  if (isOpen) return;
  isOpen = true;

  if (!panelEl) {
    panelEl = createPanel();
    wireEvents();
  }

  panelEl.style.display = "block";

  // Trigger animation
  requestAnimationFrame(() => {
    panelEl!.classList.add("open");
  });

  // Load data
  const status = await loadStatus();
  await loadPreferences();
  await loadPersonality();
  await loadGoogleStatus();

  // Check for first-time setup
  if (status && !status.env_keys_set.anthropic) {
    enterSetupMode();
  }
}

export function closeSettings() {
  if (!panelEl || !isOpen) return;
  isOpen = false;
  panelEl.classList.remove("open");
  setTimeout(() => {
    if (panelEl) panelEl.style.display = "none";
  }, 300);
}

export function isSettingsOpen(): boolean {
  return isOpen;
}

/**
 * Sync the Live Conversation toggle checkbox when main.ts toggles the mode
 * (e.g. via voice command). Call this from main.ts.
 */
export function syncInterruptibleToggle(enabled: boolean): void {
  const toggle = document.getElementById("toggle-interruptible") as HTMLInputElement | null;
  if (toggle) toggle.checked = enabled;
}

/**
 * Check if first-time setup is needed and auto-open.
 */
export async function checkFirstTimeSetup(): Promise<boolean> {
  try {
    const status = await apiGet<StatusResponse>("/api/settings/status");
    if (!status.env_keys_set.anthropic) {
      openSettings();
      return true;
    }
  } catch {
    // Server not ready yet, skip
  }
  return false;
}
