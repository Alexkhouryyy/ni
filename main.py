#!/usr/bin/env python3
"""
Voice AI Agent — talks, sees your screen, controls your computer, researches, pushes back.

Usage:
    python main.py                  # voice mode (default)
    python main.py --text           # text mode (no mic/speaker needed)
    python main.py --text --think   # text mode + extended thinking for all queries
"""
import argparse
import sys
import os
import signal
import threading

# Ensure ANTHROPIC_API_KEY is set before anything else
from dotenv import load_dotenv
load_dotenv()

import config

if not config.ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set. Create a .env file or set the environment variable.")
    sys.exit(1)


def build_parser():
    p = argparse.ArgumentParser(description="Voice AI Agent")
    p.add_argument("--text", action="store_true", help="Text I/O instead of voice")
    p.add_argument("--think", action="store_true", help="Enable extended thinking for all queries")
    p.add_argument("--no-proactive", action="store_true", help="Disable proactive screen monitoring")
    p.add_argument("--no-screenshot", action="store_true", help="Don't auto-attach screenshot to each message")
    return p


def main():
    args = build_parser().parse_args()

    if args.no_proactive:
        config.PROACTIVE_ENABLED = False

    print("\n" + "="*60)
    print("  Voice AI Agent")
    print("  Model:     ", config.AGENT_MODEL)
    print("  Mode:      ", "text" if args.text else "voice")
    print("  Thinking:  ", "on" if args.think else "auto")
    print("  Proactive: ", "on" if config.PROACTIVE_ENABLED else "off")
    print("="*60 + "\n")

    # Initialize agent
    from agent.core import AgentCore
    agent = AgentCore()

    # Initialize I/O
    if args.text:
        def speak(text: str):
            print(f"\nAGENT: {text}\n")

        def listen() -> str:
            try:
                return input("YOU: ").strip()
            except (EOFError, KeyboardInterrupt):
                return ""
    else:
        from voice.tts import speak
        from voice.stt import listen

        # Warm up TTS
        speak("Agent online. Ready.")

    # Start proactive monitor
    from agent.proactive import ProactiveMonitor
    monitor = ProactiveMonitor(agent, speak)

    shutdown_event = threading.Event()

    def shutdown(sig=None, frame=None):
        print("\n[Agent] Shutting down...")
        shutdown_event.set()
        monitor.stop()
        if not args.text:
            speak("Signing off.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    monitor.start()

    # Greeting
    greeting = (
        "I'm online. I can see your screen, run commands, search the web, and control your computer. "
        "What are we building?"
    )
    speak(greeting)

    # Main loop
    print("Press Ctrl+C to quit.\n")
    while not shutdown_event.is_set():
        # Get input
        if args.text:
            user_input = listen()
        else:
            print("[Listening...]")
            user_input = listen()

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "bye", "goodbye", "stop"}:
            shutdown()

        # Determine if this warrants deep thinking
        think = args.think or _needs_thinking(user_input)
        if think:
            print("[Thinking deeply...]")

        # Run agent
        try:
            response = agent.run(
                user_input,
                include_screenshot=not args.no_screenshot,
                use_thinking=think,
            )
        except Exception as e:
            response = f"Something went wrong: {e}"
            print(f"[Error] {e}")

        speak(response)


def _needs_thinking(text: str) -> bool:
    """Heuristic: trigger extended thinking for complex analytical or planning tasks."""
    keywords = [
        "plan", "design", "architect", "strategy", "analyze", "analyse",
        "think through", "compare", "evaluate", "pros and cons", "should i",
        "best way", "how would you", "explain why", "deep dive",
    ]
    low = text.lower()
    return any(k in low for k in keywords)


if __name__ == "__main__":
    main()
