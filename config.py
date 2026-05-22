import os
from dotenv import load_dotenv

load_dotenv()

# Model
AGENT_MODEL = os.getenv("AGENT_MODEL", "claude-opus-4-7")
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
TTS_ENGINE = os.getenv("TTS_ENGINE", "pyttsx3")  # pyttsx3 | elevenlabs | openai
TTS_RATE = 185                  # words per minute (pyttsx3)
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")   # alloy|echo|fable|onyx|nova|shimmer
OPENAI_STT_ENGINE = os.getenv("OPENAI_STT_ENGINE", "local")  # local|openai

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
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "7860"))
DASHBOARD_HOST  = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")

# OCR / vision precision
OCR_CONFIDENCE_THRESHOLD = 30

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

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
    # Anthropic
    "claude-opus-4-7":           {"input": 15.0,  "output": 75.0,  "cache_read": 1.50, "cache_create": 18.75},
    "claude-opus-4-6":           {"input": 15.0,  "output": 75.0,  "cache_read": 1.50, "cache_create": 18.75},
    "claude-sonnet-4-6":         {"input": 3.0,   "output": 15.0,  "cache_read": 0.30, "cache_create": 3.75},
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output": 4.0,   "cache_read": 0.08, "cache_create": 1.0},
    # OpenAI
    "gpt-4o":                    {"input": 2.5,   "output": 10.0,  "cache_read": 1.25, "cache_create": 0.0},
    "gpt-4o-mini":               {"input": 0.15,  "output": 0.60,  "cache_read": 0.075,"cache_create": 0.0},
    "gpt-4-turbo":               {"input": 10.0,  "output": 30.0,  "cache_read": 0.0,  "cache_create": 0.0},
    "o1":                        {"input": 15.0,  "output": 60.0,  "cache_read": 7.5,  "cache_create": 0.0},
    "o1-mini":                   {"input": 1.1,   "output": 4.4,   "cache_read": 0.55, "cache_create": 0.0},
    "o3-mini":                   {"input": 1.1,   "output": 4.4,   "cache_read": 0.55, "cache_create": 0.0},
    # Google Gemini
    "gemini-2.5-pro":            {"input": 1.25,  "output": 10.0,  "cache_read": 0.31, "cache_create": 0.0},
    "gemini-2.5-flash":          {"input": 0.30,  "output": 2.50,  "cache_read": 0.075,"cache_create": 0.0},
    "gemini-2.0-flash":          {"input": 0.10,  "output": 0.40,  "cache_read": 0.025,"cache_create": 0.0},
}

# Reflection
REFLECTION_AUTO_APPLY_THRESHOLD = 0.85

# Self-improving skills
SKILL_AUTOCREATE_MIN_TOOLS = 4   # tool calls in a turn before proposing a reusable skill

# Discord bot
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY", "")
DISCORD_DEFAULT_CHANNEL_ID = os.getenv("DISCORD_DEFAULT_CHANNEL_ID", "")
DISCORD_ALLOWED_USER_IDS = [x.strip() for x in os.getenv("DISCORD_ALLOWED_USER_IDS", "").split(",") if x.strip()]

# Slack bot
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_ALLOWED_CHANNEL_IDS = [x.strip() for x in os.getenv("SLACK_ALLOWED_CHANNEL_IDS", "").split(",") if x.strip()]

# WhatsApp (via Twilio — reuses TWILIO_SID / TWILIO_AUTH_TOKEN)
WHATSAPP_FROM_NUMBER = os.getenv("WHATSAPP_FROM_NUMBER", "")
WHATSAPP_ALLOWED_NUMBERS = [n.strip() for n in os.getenv("WHATSAPP_ALLOWED_NUMBERS", "").split(",") if n.strip()]

# Signal (via signal-cli-rest-api Docker bridge)
SIGNAL_CLI_URL = os.getenv("SIGNAL_CLI_URL", "")
SIGNAL_PHONE_NUMBER = os.getenv("SIGNAL_PHONE_NUMBER", "")
SIGNAL_ALLOWED_NUMBERS = [n.strip() for n in os.getenv("SIGNAL_ALLOWED_NUMBERS", "").split(",") if n.strip()]
