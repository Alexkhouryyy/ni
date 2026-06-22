/**
 * JARVIS — Main entry point.
 *
 * Wires together the orb visualization, WebSocket communication,
 * speech recognition, and audio playback into a single experience.
 */

import { createOrb, type OrbState } from "./orb";
import { createVoiceInput, createAudioPlayer } from "./voice";
import { createSocket } from "./ws";
import { openSettings, checkFirstTimeSetup } from "./settings";
import { handleLiveLab } from "./live-lab";
import { openCostDashboard } from "./cost-dashboard";
import "./style.css";

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type State = "idle" | "listening" | "thinking" | "speaking";
let currentState: State = "idle";
let isMuted = false;

// Live Conversation Mode — mic stays active while JARVIS speaks, enabling interruption
let interruptibleMode = localStorage.getItem("jarvis_interruptible") === "true";
let speakingStartTime = 0;  // guards against self-echo triggering false interrupts

export function setInterruptibleMode(enabled: boolean): void {
  interruptibleMode = enabled;
  localStorage.setItem("jarvis_interruptible", enabled ? "true" : "false");
}
// Expose on window so settings.ts can call it without circular imports
(window as any).__jarvis_setInterruptibleMode = setInterruptibleMode;

// Study Mode state
let studyModeActive = false;

// Brutal Honesty Mode state
let brutalModeActive = false;

// Hyper Intelligence Mode state
let hyperModeActive = false;

// Text input state
let textInputVisible = false;

const statusEl = document.getElementById("status-text")!;
const errorEl = document.getElementById("error-text")!;

function showError(msg: string) {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 5000);
}

function updateStatus(state: State) {
  const labels: Record<State, string> = {
    idle: "",
    listening: "listening...",
    thinking: "thinking...",
    speaking: "",
  };
  statusEl.textContent = labels[state];
}

// ---------------------------------------------------------------------------
// Desktop shell mode — when hosted by pywebview, behave as floating orb
// ---------------------------------------------------------------------------

const isShellMode = (() => {
  // pywebview injects window.pywebview a moment after load. Detect either via
  // the global, or via a query string we can pass from desktop_shell.py.
  if ((window as any).pywebview) return true;
  if (new URLSearchParams(window.location.search).get("shell") === "1") return true;
  // User-agent heuristic: pywebview uses Edge WebView2 on Windows, but so does
  // a regular Edge browser, so prefer the explicit signals above.
  return false;
})();

if (isShellMode) {
  document.body.classList.add("shell-mode", "shell-collapsed");
  // Auto-collapse when user switches to another app
  window.addEventListener("blur", () => {
    if (document.body.classList.contains("shell-expanded")) {
      collapseShell();
    }
  });
}

function expandShell(): void {
  document.body.classList.remove("shell-collapsed");
  document.body.classList.add("shell-expanded");
  try { (window as any).pywebview?.api?.expand(); } catch {}
}

function collapseShell(): void {
  document.body.classList.remove("shell-expanded");
  document.body.classList.add("shell-collapsed");
  try { (window as any).pywebview?.api?.collapse(); } catch {}
}

(window as any).__jarvis_expandShell = expandShell;
(window as any).__jarvis_collapseShell = collapseShell;

// ---------------------------------------------------------------------------
// Init components
// ---------------------------------------------------------------------------

const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
const orb = createOrb(canvas);

// In shell mode, clicking the orb expands the panel
if (isShellMode) {
  canvas.addEventListener("click", () => {
    if (document.body.classList.contains("shell-collapsed")) {
      expandShell();
    }
  });
}

const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
const WS_URL = `${wsProto}//${window.location.host}/ws/voice`;
const socket = createSocket(WS_URL);

const audioPlayer = createAudioPlayer();
orb.setAnalyser(audioPlayer.getAnalyser());

// Study Mode window bridges (must come after orb + socket are created)
(window as any).__jarvis_setStudyMode = (enabled: boolean) => {
  studyModeActive = enabled;
  orb.setStudyMode(enabled);
  const studyBadge = document.getElementById("study-mode-badge");
  if (studyBadge) studyBadge.style.display = enabled ? "block" : "none";
};
(window as any).__jarvis_sendStudyEnd = () => {
  socket.send({ type: "study_end" });
};

(window as any).__jarvis_setBrutalMode = (enabled: boolean) => {
  brutalModeActive = enabled;
  orb.setBrutalMode(enabled);
  const brutalBadge = document.getElementById("brutal-mode-badge");
  if (brutalBadge) brutalBadge.style.display = enabled ? "block" : "none";
};

(window as any).__jarvis_setHyperMode = (enabled: boolean) => {
  hyperModeActive = enabled;
  orb.setHyperMode(enabled);
  const hyperBadge = document.getElementById("hyper-mode-badge");
  if (hyperBadge) hyperBadge.style.display = enabled ? "block" : "none";
};

function transition(newState: State) {
  if (newState === currentState) return;
  currentState = newState;
  orb.setState(newState as OrbState);
  updateStatus(newState);

  switch (newState) {
    case "idle":
      if (!isMuted) voiceInput.resume();
      break;
    case "listening":
      if (!isMuted) voiceInput.resume();
      break;
    case "thinking":
      voiceInput.pause();  // always pause during thinking — brief, not worth interrupting
      break;
    case "speaking":
      speakingStartTime = Date.now();
      // Live Conversation Mode: keep mic ON so user can interrupt mid-sentence
      // Normal mode: pause mic to avoid feedback
      if (!interruptibleMode) voiceInput.pause();
      break;
  }
}

// ---------------------------------------------------------------------------
// Voice input
// ---------------------------------------------------------------------------

const voiceInput = createVoiceInput(
  // ── Final transcript ──
  (text: string) => {
    audioPlayer.stop();
    socket.send({
      type: "transcript",
      text,
      isFinal: true,
      streaming: interruptibleMode,  // tells server to use streaming pipeline
    });
    transition("thinking");
  },
  // ── Error ──
  (msg: string) => {
    showError(msg);
  },
  // ── Interim speech (Live Conversation Mode interrupt detection) ──
  (interimText: string, confidence: number) => {
    if (!interruptibleMode) return;
    if (currentState !== "speaking") return;
    // Dead-zone: ignore first 800ms to let JARVIS start speaking without self-triggering
    if (Date.now() - speakingStartTime < 800) return;
    // Require at least 2 words to avoid single-syllable noise
    const wordCount = interimText.trim().split(/\s+/).length;
    if (wordCount < 2) return;
    // Confidence guard (0 means engine didn't provide confidence — allow through)
    if (confidence > 0 && confidence < 0.55) return;

    console.log("[interrupt] detected:", interimText, "confidence:", confidence);
    audioPlayer.stop();
    socket.send({ type: "interrupt" });
    transition("listening");
  }
);

// ---------------------------------------------------------------------------
// Audio playback finished
// ---------------------------------------------------------------------------

audioPlayer.onFinished(() => {
  transition("idle");
});

// ---------------------------------------------------------------------------
// WebSocket messages
// ---------------------------------------------------------------------------

socket.onMessage((msg) => {
  const type = msg.type as string;

  if (type === "audio") {
    const audioData = msg.data as string;
    console.log("[audio] received", audioData ? `${audioData.length} chars` : "EMPTY", "state:", currentState);
    if (audioData) {
      if (currentState !== "speaking") {
        transition("speaking");
      }
      audioPlayer.enqueue(audioData);
    } else {
      // TTS failed — no audio but still need to return to idle
      console.warn("[audio] no data received, returning to idle");
      transition("idle");
    }
    // Log text for debugging
    if (msg.text) console.log("[JARVIS]", msg.text);
  } else if (type === "status") {
    const state = msg.state as string;
    if (state === "thinking" && currentState !== "thinking") {
      transition("thinking");
    } else if (state === "working") {
      // Task spawned — show thinking with a different label
      transition("thinking");
      statusEl.textContent = "working...";
    } else if (state === "idle") {
      transition("idle");
    }
  } else if (type === "text") {
    // Text fallback when TTS fails
    console.log("[JARVIS]", msg.text);
  } else if (type === "task_spawned") {
    console.log("[task]", "spawned:", msg.task_id, msg.prompt);
  } else if (type === "task_complete") {
    console.log("[task]", "complete:", msg.task_id, msg.status, msg.summary);
  } else if (type === "live_lab") {
    handleLiveLab(msg as any);
  }
});

// ---------------------------------------------------------------------------
// Kick off
// ---------------------------------------------------------------------------

// Start listening after a brief delay for the orb to render
setTimeout(() => {
  voiceInput.start();
  transition("listening");
}, 1000);

// Resume AudioContext on ANY user interaction (browser autoplay policy)
function ensureAudioContext() {
  const ctx = audioPlayer.getAnalyser().context as AudioContext;
  if (ctx.state === "suspended") {
    ctx.resume().then(() => console.log("[audio] context resumed"));
  }
}
document.addEventListener("click", ensureAudioContext);
document.addEventListener("touchstart", ensureAudioContext);
document.addEventListener("keydown", ensureAudioContext, { once: true });

// Try to resume audio context on load
ensureAudioContext();

// ---------------------------------------------------------------------------
// UI Controls
// ---------------------------------------------------------------------------

const btnMute = document.getElementById("btn-mute")!;
const btnMenu = document.getElementById("btn-menu")!;
const menuDropdown = document.getElementById("menu-dropdown")!;
const btnRestart = document.getElementById("btn-restart")!;
const btnFixSelf = document.getElementById("btn-fix-self")!;

btnMute.addEventListener("click", (e) => {
  e.stopPropagation();
  isMuted = !isMuted;
  btnMute.classList.toggle("muted", isMuted);
  if (isMuted) {
    voiceInput.pause();
    transition("idle");
    showTextInput();   // can't speak → offer keyboard
  } else {
    hideTextInput();
    voiceInput.resume();
    transition("listening");
  }
});

btnMenu.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = menuDropdown.style.display === "none" ? "block" : "none";
});

document.addEventListener("click", () => {
  menuDropdown.style.display = "none";
});

btnRestart.addEventListener("click", async (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  statusEl.textContent = "restarting...";
  try {
    await fetch("/api/restart", { method: "POST" });
    // Wait a few seconds then reload
    setTimeout(() => window.location.reload(), 4000);
  } catch {
    statusEl.textContent = "restart failed";
  }
});

btnFixSelf.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  // Activate work mode on the WebSocket session (JARVIS becomes Claude Code's voice)
  socket.send({ type: "fix_self" });
  statusEl.textContent = "entering work mode...";
});

// Cost Dashboard — slide-in panel showing spend / breakdowns / recent calls
const btnCostDashboard = document.getElementById("btn-cost-dashboard");
btnCostDashboard?.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  openCostDashboard();
});

// Floating Orb — launch the desktop_shell.py companion window
const btnFloatingOrb = document.getElementById("btn-floating-orb");
btnFloatingOrb?.addEventListener("click", async (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  statusEl.textContent = "launching orb...";
  try {
    const res = await fetch("/api/desktop/launch-orb", { method: "POST" });
    if (res.ok) {
      statusEl.textContent = "orb launched";
      setTimeout(() => { statusEl.textContent = ""; }, 3000);
    } else {
      statusEl.textContent = "orb launch failed";
    }
  } catch {
    statusEl.textContent = "orb launch failed";
  }
});

// Settings button
const btnSettings = document.getElementById("btn-settings")!;
btnSettings.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  openSettings();
});

// ---------------------------------------------------------------------------
// Keyboard / text input
// ---------------------------------------------------------------------------

const textInputBar = document.getElementById("text-input-bar")!;
const textInputEl = document.getElementById("text-input") as HTMLInputElement;
const textSendBtn = document.getElementById("text-send-btn")!;
const btnKeyboard = document.getElementById("btn-keyboard")!;

function showTextInput() {
  textInputVisible = true;
  textInputBar.classList.add("visible");
  btnKeyboard.classList.add("active");
  // Small delay so the slide-up animation plays before focusing
  setTimeout(() => textInputEl.focus(), 60);
}

function hideTextInput() {
  textInputVisible = false;
  textInputBar.classList.remove("visible");
  btnKeyboard.classList.remove("active");
  textInputEl.blur();
}

function sendTextMessage() {
  const text = textInputEl.value.trim();
  if (!text) return;
  audioPlayer.stop();
  socket.send({ type: "transcript", text, isFinal: true, streaming: interruptibleMode });
  transition("thinking");
  textInputEl.value = "";
  hideTextInput();
}

btnKeyboard.addEventListener("click", (e) => {
  e.stopPropagation();
  textInputVisible ? hideTextInput() : showTextInput();
});

textInputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); sendTextMessage(); }
  if (e.key === "Escape") hideTextInput();
});

textSendBtn.addEventListener("click", sendTextMessage);

// Dismiss when clicking outside the bar (menuDropdown click-outside already exists)
document.addEventListener("click", (e) => {
  if (
    textInputVisible &&
    !textInputBar.contains(e.target as Node) &&
    e.target !== btnKeyboard
  ) {
    hideTextInput();
  }
});

// Window bridge — lets settings.ts or other modules open the keyboard programmatically
(window as any).__jarvis_showKeyboard = showTextInput;

// First-time setup detection — check after a short delay for server readiness
setTimeout(() => {
  checkFirstTimeSetup();
}, 2000);
