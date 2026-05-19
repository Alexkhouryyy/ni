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
    p.add_argument("--wake", action="store_true", help="Hands-free wake word mode (say 'hey agent')")
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

    # Initialize agent + long-term memory
    from agent.core import AgentCore
    from agent import longterm
    longterm.init_db()
    session_id = longterm.start_session()
    print(f"[Memory] Session #{session_id} started. DB: {longterm.DB_PATH}")

    # Load top memories into the agent's working context as a system reminder
    memories = longterm.top_memories(limit=15)
    if memories:
        print(f"[Memory] Loaded {len(memories)} long-term memories.")
    agent = AgentCore()
    if memories:
        agent.memory.summary = longterm.format_for_context(memories)

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
        try:
            longterm.end_session(session_id, summary=agent.memory.summary)
        except Exception:
            pass
        try:
            from tools import browser as _b
            _b.close()
        except Exception:
            pass
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

    # Wake word mode setup
    wake_event = threading.Event()
    wake_listener = None
    if args.wake and not args.text:
        from voice.wake import WakeWordListener
        wake_listener = WakeWordListener(wake_phrases=config.WAKE_PHRASES)
        wake_listener.start(on_wake=wake_event.set)
        speak("Wake mode on. Say 'hey agent' to wake me.")

    # Main loop
    print("Press Ctrl+C to quit.\n")
    while not shutdown_event.is_set():
        # Get input
        if args.text:
            user_input = listen()
        elif args.wake:
            # Wait for wake trigger, then do full listen
            wake_event.wait()
            wake_event.clear()
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

        # Run agent — streaming when we have voice output for low-latency speak
        try:
            if args.text:
                response = agent.run(
                    user_input,
                    include_screenshot=not args.no_screenshot,
                    use_thinking=think,
                )
                speak(response)
            else:
                from voice.streamer import StreamingSpeaker
                streamer = StreamingSpeaker()
                streamer.start()
                response = agent.run(
                    user_input,
                    include_screenshot=not args.no_screenshot,
                    use_thinking=think,
                    streamer=streamer,
                )
                streamer.finish()
                print(f"\nAGENT: {response}\n")
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
