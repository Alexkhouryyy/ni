import os
from dotenv import load_dotenv

load_dotenv()

# Model
AGENT_MODEL = "claude-opus-4-7"
PROACTIVE_MODEL = "claude-haiku-4-5-20251001"
THINKING_BUDGET = 8000  # tokens for extended thinking

# API resilience
API_MAX_RETRIES = 4  # transient errors (429/500/529/network) retried by the SDK with exponential backoff
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "anthropic/claude-3-5-sonnet")

# Voice
WHISPER_MODEL = "base"          # tiny/base/small/medium/large
WHISPER_DEVICE = "cpu"          # cpu or cuda
SILENCE_THRESHOLD = 0.01        # RMS threshold to detect silence
SILENCE_DURATION = 1.5          # seconds of silence before stopping recording
MAX_RECORD_SECONDS = 60         # hard cap on recording length
SAMPLE_RATE = 16000

# TTS
TTS_ENGINE = "pyttsx3"          # pyttsx3 or elevenlabs
TTS_RATE = 185                  # words per minute (pyttsx3)
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

# Proactive monitor
PROACTIVE_INTERVAL = 30         # seconds between screen checks
PROACTIVE_ENABLED = True

# Wake word
WAKE_WORD_ENABLED = False       # set to True for hands-free always-on mode
WAKE_PHRASES = ["hey agent", "okay agent", "ok agent"]

# Awareness watchers
AWARENESS_ENABLED = True
AWARENESS_REVIEW_INTERVAL = 60        # seconds — how often to review event log
AWARENESS_WATCH_PATHS = [             # file watcher dirs
    "~/Documents", "~/Desktop", "~/Downloads",
]

# Knowledge base
KB_INDEX_PATHS = [                    # paths to index for RAG
    "~/Documents/notes",
]

# Multi-agent
MAX_SUBAGENTS = 5                     # max concurrent sub-agents
MAX_ITERATIONS = 30                   # max tool-use iterations per agent turn

# Dashboard
DASHBOARD_ENABLED = True
DASHBOARD_PORT = 7860

# OCR / vision precision
OCR_CONFIDENCE_THRESHOLD = 30

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# Research
MAX_SEARCH_RESULTS = 6
MAX_PAGE_CONTENT_CHARS = 8000

# Bash
BASH_TIMEOUT = 30               # seconds

# Screen
SCREENSHOT_QUALITY = 85         # JPEG quality for screenshots sent to Claude

# === Tier-4 ===

# Voice (streaming)
PARTIAL_INTERVAL_MS = 500       # how often to re-transcribe the rolling buffer

# Phone (Twilio)
TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
PHONE_ALLOWED_NUMBERS = [n.strip() for n in os.getenv("PHONE_ALLOWED_NUMBERS", "").split(",") if n.strip()]

# Telegram bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_CHAT_IDS = [x.strip() for x in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if x.strip()]

# Image generation (Replicate)
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
IMAGE_GEN_MODEL = os.getenv("IMAGE_GEN_MODEL", "black-forest-labs/flux-schnell")
IMAGE_GEN_OUTPUT_DIR = os.getenv("IMAGE_GEN_OUTPUT_DIR", "~/.voice_agent_images")

# Telemetry — Anthropic per-million-token pricing (USD)
# Update when models / prices change.
MODEL_PRICING = {
    "claude-opus-4-7":           {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_create": 18.75},
    "claude-opus-4-6":           {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_create": 18.75},
    "claude-sonnet-4-6":         {"input": 3.0,  "output": 15.0, "cache_read": 0.30, "cache_create": 3.75},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0,  "cache_read": 0.08, "cache_create": 1.0},
}

# Reflection
REFLECTION_AUTO_APPLY_THRESHOLD = 0.85
