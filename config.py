import os
from dotenv import load_dotenv

load_dotenv()

# Model
AGENT_MODEL = "claude-opus-4-7"
PROACTIVE_MODEL = "claude-haiku-4-5-20251001"
THINKING_BUDGET = 8000  # tokens for extended thinking

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
