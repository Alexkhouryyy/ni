#!/usr/bin/env python3
"""
Voice AI Agent — talks, sees your screen, controls your computer, researches, pushes back.

Usage:
    python main.py                  # voice mode (default)
    python main.py --text           # text mode (no mic/speaker needed)
    python main.py --text --think   # text mode + extended thinking for all queries
"""
import argparse
import os
import signal
import sys
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
    p.add_argument("--tui", action="store_true", help="Rich terminal UI: streaming output + interrupt-and-redirect")
    p.add_argument("--think", action="store_true", help="Enable extended thinking for all queries")
    p.add_argument("--no-proactive", action="store_true", help="Disable proactive screen monitoring")
    p.add_argument("--no-screenshot", action="store_true", help="Don't auto-attach screenshot to each message")
    p.add_argument("--wake", action="store_true", help="Hands-free wake word mode (say 'hey agent')")
    p.add_argument("--model", type=str, default=None, help="Override starting model (e.g. gpt-4o, claude-sonnet-4-6)")
    return p


def main():
    args = build_parser().parse_args()

    if args.no_proactive:
        config.PROACTIVE_ENABLED = False

    print("\n" + "="*60)
    print("  Voice AI Agent")
    print("  Model:     ", config.AGENT_MODEL)
    print("  Mode:      ", "tui" if args.tui else ("text" if args.text else "voice"))
    print("  Thinking:  ", "on" if args.think else "auto")
    print("  Proactive: ", "on" if config.PROACTIVE_ENABLED else "off")
    print("  Wake word: ", "on" if args.wake else "off")
    print("="*60 + "\n")

    # Initialize agent + long-term memory
    from agent.core import AgentCore
    from agent import longterm, telemetry
    longterm.init_db()
    session_id = longterm.start_session()
    telemetry.set_session(session_id)
    print(f"[Memory] Session #{session_id} started. DB: {longterm.DB_PATH}")

    # Load top memories into the agent's working context as a system reminder
    memories = longterm.top_memories(limit=15)
    if memories:
        print(f"[Memory] Loaded {len(memories)} long-term memories.")
    agent = AgentCore()
    if args.model:
        result = agent.set_model(args.model)
        print(f"[Model] {result}")
    if memories:
        agent.memory.summary = longterm.format_for_context(memories)

    # MCP tool discovery (non-blocking — happens in background)
    import threading
    def _load_mcp():
        n = agent.load_mcp_tools()
        if n:
            speak(f"Connected {n} MCP tools.")
    threading.Thread(target=_load_mcp, daemon=True, name="MCPDiscover").start()

    # Initialize I/O
    if args.text or args.tui:
        def speak(text: str):
            print(f"\nAGENT: {text}\n")

        def listen() -> str:
            try:
                return input("YOU: ").strip()
            except (EOFError, KeyboardInterrupt):
                return ""
    else:
        from voice.tts import speak
        from voice.stt import listen, listen_streaming, warm_up as _stt_warm

        # Pre-warm Whisper kernel so the first real turn is fast
        threading.Thread(target=_stt_warm, daemon=True, name="STTWarmup").start()

        # Warm up TTS
        speak("Agent online. Ready.")

    # Wire safety confirmation to speak+listen
    from agent import safety as _safety
    def _voice_confirm(reason: str) -> bool:
        speak(f"Safety check. {reason}. Say yes to proceed.")
        answer = listen() if not (args.text or args.tui) else input("Proceed? (y/N): ").strip()
        return answer.lower() in {"yes", "y", "yeah", "yep", "do it", "confirm"}
    _safety.set_confirm_fn(_voice_confirm)

    # Start scheduler
    from agent import scheduler as sched
    sched.init(agent_run_fn=agent.run, speak_fn=speak)

    # Wire orchestrator with a fresh-agent factory (no shared memory)
    from agent import orchestrator
    def _sub_factory():
        from agent.core import AgentCore
        return AgentCore()
    orchestrator.set_agent_factory(_sub_factory)

    # Load self-mod overlay (system prompt addition + dynamic tools)
    from agent import self_mod
    n_dyn = self_mod.load_dynamic_handlers()
    if n_dyn:
        print(f"[SelfMod] Loaded {n_dyn} user-defined tools.")

    # Load skills registry
    from agent import skills as skills_mod
    n_skills = skills_mod.load_all()
    if n_skills:
        print(f"[Skills] Loaded {n_skills} skill(s).")

    # Knowledge base — ensure schema, optionally trigger background indexing
    from agent import knowledge
    knowledge.init_db()

    # Goals — init tables + auto-schedule weekly self-eval (once per fresh DB)
    from agent import goals
    goals.init_db()
    weekly_eval_exists = any(
        "Weekly self-evaluation" in t.get("description", "") for t in sched.list_tasks()
    )
    if not weekly_eval_exists:
        sched.schedule(
            description=(
                "Weekly self-evaluation. Call evaluate_recent_work(days=7) and speak the result. "
                "Then suggest one concrete focus for the coming week."
            ),
            trigger_type="cron",
            trigger_params={"day_of_week": "mon", "hour": 8, "minute": 0},
        )

    # Nightly reflection — once per fresh DB
    from agent import reflection
    nightly_refl_exists = any(
        "Nightly reflection" in t.get("description", "") for t in sched.list_tasks()
    )
    if not nightly_refl_exists:
        sched.schedule(
            description=(
                "Nightly reflection. Call reflect_now(hours=24). Then call list_reflections(status='pending') "
                "and briefly mention how many insights are awaiting review on the dashboard."
            ),
            trigger_type="cron",
            trigger_params={"hour": 3, "minute": 0},
        )

    # Twilio inbound dispatch — wire agent.run so SMS/voice webhooks have a brain
    from tools import phone as _phone
    def _phone_agent_run(text: str, *, channel_id: str | None = None) -> str:
        try:
            return agent.run(text, include_screenshot=False, use_thinking=False, channel_id=channel_id)
        except Exception as e:
            return f"Agent error: {e}"
    _phone.set_agent_run_fn(_phone_agent_run)

    # Telegram inbound dispatch
    from tools import telegram as _telegram
    def _telegram_agent_run(text: str, *, channel_id: str | None = None) -> str:
        try:
            return agent.run(text, include_screenshot=False, use_thinking=False, channel_id=channel_id)
        except Exception as e:
            return f"Agent error: {e}"
    _telegram.set_agent_run_fn(_telegram_agent_run)

    # Discord inbound dispatch
    from tools import discord as _discord
    def _discord_agent_run(text: str, *, channel_id: str | None = None) -> str:
        try:
            return agent.run(text, include_screenshot=False, use_thinking=False, channel_id=channel_id)
        except Exception as e:
            return f"Agent error: {e}"
    _discord.set_agent_run_fn(_discord_agent_run)

    # Awareness monitor (replaces old screenshot-only proactive)
    if config.AWARENESS_ENABLED:
        from agent.awareness import AwarenessMonitor

        def _awareness_proactive_check(events_summary: str):
            """Lightweight Haiku call: decide if events warrant interrupting."""
            try:
                resp = telemetry.create(
                    agent.anthropic,
                    call_site="agent.awareness/review",
                    model=config.PROACTIVE_MODEL,
                    max_tokens=200,
                    messages=[{"role": "user", "content": (
                        "You watch the user's desktop in the background. "
                        "Recent events (last ~90s):\n\n" + events_summary + "\n\n"
                        "Is there anything URGENT or genuinely useful to proactively bring up RIGHT NOW? "
                        "Examples that warrant interrupting: an error in their work, a security concern, "
                        "they look stuck on something obvious you could help with, an opportunity they'll miss. "
                        "Examples that DON'T: normal app switching, routine copy-paste, mundane file edits. "
                        "If YES, respond with a single short observation (1 sentence). "
                        "If NO, respond with exactly: NO"
                    )}],
                )
                text = resp.content[0].text.strip()
                return None if text.upper().startswith("NO") else text
            except Exception:
                return None

        awareness_paths = [os.path.expanduser(p) for p in config.AWARENESS_WATCH_PATHS]
        monitor = AwarenessMonitor(
            agent_proactive_check=_awareness_proactive_check,
            speak_fn=speak,
            watch_paths=awareness_paths,
            review_interval=config.AWARENESS_REVIEW_INTERVAL,
        )
    else:
        # Fall back to original screenshot-only proactive
        from agent.proactive import ProactiveMonitor
        monitor = ProactiveMonitor(agent, speak)

    # Let reflection pull awareness events at consolidation time
    if hasattr(monitor, "log"):
        reflection.set_awareness_drain(lambda: monitor.log.recent(since_seconds=86400))

    # Start the web dashboard
    if getattr(config, "DASHBOARD_ENABLED", True):
        try:
            from dashboard import server as dash
            dash.set_agent(agent, awareness_log=getattr(monitor, "log", None))
            # Hook awareness events into the WebSocket broadcaster
            if hasattr(monitor, "log"):
                _orig_add = monitor.log.add
                def _add_and_broadcast(source, content):
                    _orig_add(source, content)
                    dash.ws_manager.broadcast_threadsafe({
                        "type": "event", "ts": __import__("time").time(),
                        "source": source, "content": content,
                    })
                monitor.log.add = _add_and_broadcast
            port = getattr(config, "DASHBOARD_PORT", 7860)
            host = getattr(config, "DASHBOARD_HOST", "127.0.0.1")
            dash.start_in_background(port=port)
            print(f"[Dashboard] http://{host}:{port}")
        except Exception as e:
            print(f"[Dashboard] Failed to start: {e}")

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
        try:
            from tools import repl as _r
            _r.shutdown()
        except Exception:
            pass
        if not args.text:
            speak("Signing off.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    monitor.start()

    # TUI mode: hand off to the terminal UI, which owns the input loop.
    if args.tui:
        from tui.app import run_tui
        try:
            run_tui(agent)
        finally:
            shutdown()
        return

    # Greeting
    greeting = (
        "I'm online. I can see your screen, run commands, search the web, and control your computer. "
        "What are we building?"
    )
    speak(greeting)

    # Wake word mode setup
    wake_event = threading.Event()
    wake_listener = None
    if args.wake and not args.text and not args.tui:
        from voice.wake import WakeWordListener
        wake_listener = WakeWordListener(wake_phrases=config.WAKE_PHRASES)
        wake_listener.start(on_wake=wake_event.set)
        speak("Wake mode on. Say 'hey agent' to wake me.")

    # Stream STT partials to the dashboard if it's running
    def _on_partial(text: str):
        try:
            if config.DASHBOARD_ENABLED:
                from dashboard import server as _dash
                _dash.ws_manager.broadcast_threadsafe({
                    "type": "event", "ts": __import__("time").time(),
                    "source": "stt", "content": f"… {text}",
                })
        except Exception:
            pass

    def _voice_listen():
        if args.text:
            return listen()
        try:
            return listen_streaming(on_partial=_on_partial)
        except Exception as e:
            print(f"[STT] Streaming failed ({e}), falling back to listen().")
            return listen()

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
            user_input = _voice_listen()
        else:
            print("[Listening...]")
            user_input = _voice_listen()

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "bye", "goodbye", "stop"}:
            shutdown()

        # /model command — switch providers at runtime
        if user_input.startswith("/model"):
            parts = user_input.split(None, 1)
            if len(parts) < 2:
                from agent.provider import KNOWN_MODELS
                current = agent._model
                speak(f"Current model: {current}\nAvailable: {', '.join(sorted(KNOWN_MODELS))}")
            else:
                result = agent.set_model(parts[1].strip())
                speak(result)
            continue

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
