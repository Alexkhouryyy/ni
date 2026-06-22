/**
 * JARVIS Mobile PWA — main entry point.
 *
 * Minimal voice interface: connects to JARVIS backend via WebSocket,
 * captures speech via Web Speech API, plays TTS audio via AudioContext.
 */

import "./style.css";

// ---------------------------------------------------------------------------
// Config (persisted in localStorage)
// ---------------------------------------------------------------------------

const STORAGE_KEY = "jarvis_server_ip";

function getServerIp(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

function saveServerIp(ip: string) {
  localStorage.setItem(STORAGE_KEY, ip.trim());
}

function buildWsUrl(ip: string): string {
  return `wss://${ip.trim()}:8340/ws/voice`;
}

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------

const setupScreen  = document.getElementById("setup-screen")!;
const mainScreen   = document.getElementById("main-screen")!;
const inputIp      = document.getElementById("input-server-ip") as HTMLInputElement;
const btnConnect   = document.getElementById("btn-connect")!;
const certUrlEl    = document.getElementById("cert-url")!;
const orbEl        = document.getElementById("orb")!;
const statusEl     = document.getElementById("status-text")!;
const transcriptEl = document.getElementById("transcript")!;
const btnMic       = document.getElementById("btn-mic")!;
const micLabel     = document.getElementById("mic-label")!;
const connDot      = document.getElementById("conn-dot")!;
const btnSettings  = document.getElementById("btn-settings-main")!;

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type AppState = "idle" | "listening" | "thinking" | "speaking";
let appState: AppState = "idle";
let isMicOn = false;

function setState(s: AppState) {
  appState = s;
  orbEl.className = s === "idle" ? "" : s;

  const labels: Record<AppState, string> = {
    idle:      "",
    listening: "listening...",
    thinking:  "thinking...",
    speaking:  "speaking...",
  };
  statusEl.textContent = labels[s];

  if (s === "thinking" || s === "speaking") {
    voiceInput?.pause();
  } else if (isMicOn) {
    voiceInput?.resume();
  }
}

function showTranscript(text: string, isJarvis = false) {
  transcriptEl.textContent = text;
  transcriptEl.className = "transcript" + (isJarvis ? " jarvis" : "");
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------

let ws: WebSocket | null = null;
let reconnectTimer: number | null = null;
let reconnectDelay = 1000;
let serverIp = "";

function setConnDot(state: "off" | "on" | "err") {
  connDot.className = "conn-dot conn-" + state;
}

function connectWs(ip: string) {
  serverIp = ip;
  if (ws) { ws.onclose = null; ws.close(); ws = null; }
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }

  const url = buildWsUrl(ip);
  ws = new WebSocket(url);

  ws.onopen = () => {
    reconnectDelay = 1000;
    setConnDot("on");
    setState("idle");
    if (isMicOn) voiceInput?.resume();
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data as string) as Record<string, unknown>;
      handleMessage(msg);
    } catch {
      // ignore
    }
  };

  ws.onclose = () => {
    setConnDot("err");
    reconnectTimer = window.setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 30_000);
      connectWs(serverIp);
    }, reconnectDelay);
  };

  ws.onerror = () => ws?.close();
}

function sendWs(data: Record<string, unknown>) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

// ---------------------------------------------------------------------------
// Message handler
// ---------------------------------------------------------------------------

function handleMessage(msg: Record<string, unknown>) {
  const type = msg.type as string;

  if (type === "audio") {
    const b64 = msg.data as string;
    if (b64) {
      setState("speaking");
      if (msg.text) showTranscript(msg.text as string, true);
      audioPlayer.enqueue(b64);
    } else {
      setState("idle");
    }
  } else if (type === "status") {
    const s = msg.state as string;
    if (s === "thinking" || s === "working") setState("thinking");
    else if (s === "idle") setState("idle");
  } else if (type === "text") {
    if (msg.text) showTranscript(msg.text as string, true);
  }
}

// ---------------------------------------------------------------------------
// Audio player
// ---------------------------------------------------------------------------

const audioPlayer = (() => {
  let ctx: AudioContext | null = null;
  const queue: AudioBuffer[] = [];
  let playing = false;
  let src: AudioBufferSourceNode | null = null;

  function getCtx() {
    if (!ctx) ctx = new AudioContext();
    return ctx;
  }

  function playNext() {
    if (queue.length === 0) {
      playing = false;
      setState("idle");
      return;
    }
    playing = true;
    const buf = queue.shift()!;
    const s = getCtx().createBufferSource();
    s.buffer = buf;
    s.connect(getCtx().destination);
    src = s;
    s.onended = () => { if (src === s) playNext(); };
    s.start();
  }

  return {
    async enqueue(b64: string) {
      const c = getCtx();
      if (c.state === "suspended") await c.resume();
      try {
        const bytes = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
        const buf = await c.decodeAudioData(bytes.buffer.slice(0));
        queue.push(buf);
        if (!playing) playNext();
      } catch (e) {
        console.error("[audio] decode error", e);
        if (!playing && queue.length > 0) playNext();
      }
    },
    stop() {
      queue.length = 0;
      try { src?.stop(); } catch { /**/ }
      src = null;
      playing = false;
    },
    resume() { getCtx().state === "suspended" && getCtx().resume(); },
  };
})();

// ---------------------------------------------------------------------------
// Voice input (Web Speech API)
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

interface VoiceController { start(): void; stop(): void; pause(): void; resume(): void; }
let voiceInput: VoiceController | null = null;

function createVoice(): VoiceController {
  if (!SR) {
    statusEl.textContent = "Speech recognition not supported";
    return { start() {}, stop() {}, pause() {}, resume() {} };
  }
  const rec = new SR();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = "en-US";

  let active = false;
  let paused = false;

  rec.onresult = (e: any) => {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) {
        const text = r[0].transcript.trim();
        if (text) {
          audioPlayer.stop();
          showTranscript(text, false);
          sendWs({ type: "transcript", text, isFinal: true });
          setState("thinking");
        }
      }
    }
  };

  rec.onend = () => { if (active && !paused) { try { rec.start(); } catch { /**/ } } };
  rec.onerror = (e: any) => {
    if (e.error === "not-allowed") {
      showTranscript("Microphone access denied.");
      active = false;
      isMicOn = false;
      btnMic.classList.remove("active");
      micLabel.textContent = "Tap to speak";
    }
  };

  return {
    start() { active = true; paused = false; try { rec.start(); } catch { /**/ } },
    stop()  { active = false; paused = false; rec.stop(); },
    pause() { paused = true; rec.stop(); },
    resume(){ paused = false; if (active) { try { rec.start(); } catch { /**/ } } },
  };
}

// ---------------------------------------------------------------------------
// Mic button
// ---------------------------------------------------------------------------

btnMic.addEventListener("click", () => {
  audioPlayer.resume();

  if (!isMicOn) {
    isMicOn = true;
    btnMic.classList.add("active");
    micLabel.textContent = "Listening...";
    if (!voiceInput) voiceInput = createVoice();
    voiceInput.start();
    setState("listening");
  } else {
    isMicOn = false;
    btnMic.classList.remove("active");
    micLabel.textContent = "Tap to speak";
    voiceInput?.stop();
    setState("idle");
  }
});

// Tap anywhere on orb = toggle mic
document.getElementById("orb-container")!.addEventListener("click", () => {
  btnMic.click();
});

// Resume AudioContext on any touch (iOS policy)
document.addEventListener("touchstart", () => audioPlayer.resume(), { once: true });
document.addEventListener("click", () => audioPlayer.resume(), { once: true });

// ---------------------------------------------------------------------------
// Settings button (re-show setup)
// ---------------------------------------------------------------------------

btnSettings.addEventListener("click", () => {
  mainScreen.style.display = "none";
  setupScreen.style.display = "flex";
  const ip = getServerIp() || "";
  inputIp.value = ip;
  certUrlEl.textContent = ip ? `https://${ip}:8340` : "https://<ip>:8340";
});

// ---------------------------------------------------------------------------
// Setup screen
// ---------------------------------------------------------------------------

function showMain(ip: string) {
  setupScreen.style.display = "none";
  mainScreen.style.display = "flex";
  if (!voiceInput) voiceInput = createVoice();
  connectWs(ip);
}

btnConnect.addEventListener("click", () => {
  const ip = inputIp.value.trim();
  if (!ip) { inputIp.focus(); return; }
  saveServerIp(ip);
  showMain(ip);
});

inputIp.addEventListener("keydown", (e) => {
  if (e.key === "Enter") btnConnect.click();
});

inputIp.addEventListener("input", () => {
  const ip = inputIp.value.trim();
  certUrlEl.textContent = ip ? `https://${ip}:8340` : "https://<ip>:8340";
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

const savedIp = getServerIp();
if (savedIp) {
  showMain(savedIp);
} else {
  setupScreen.style.display = "flex";
  certUrlEl.textContent = "https://<ip>:8340";
}

// Register service worker
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
