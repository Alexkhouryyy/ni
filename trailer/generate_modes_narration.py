"""
Generate modes showcase narration MP3 via OpenAI TTS (onyx voice).
Run: python generate_modes_narration.py
Output: public/audio/modes_narration.mp3
"""
import os, sys, pathlib

try:
    from openai import OpenAI
except ImportError:
    print("Installing openai...")
    os.system(f"{sys.executable} -m pip install openai")
    from openai import OpenAI

client = OpenAI()

SCRIPT = """
JARVIS is already extraordinary. But what if JARVIS could shift personality — on demand — based on exactly what you need in this moment?

Six modes. Six different JARVISes.

Focus Mode. When you need to get things done. No tangents. No small talk. Pure execution. JARVIS locks in with you. Every response moves the needle.

Brutal Honesty Mode. When you need the truth, not flattery. You show JARVIS your business plan. He finds every flaw. Every gap. No sugar-coating. That's what makes it valuable.

Health Coach Mode. Your wellness companion. Sleep, nutrition, movement, mental health. JARVIS tracks your habits and holds you accountable — because small consistent actions build extraordinary lives.

Debate Mode. JARVIS argues against you — on purpose. You present an idea. He stress-tests it. Pokes holes. Plays devil's advocate. Ideas that survive JARVIS's debate are ideas worth keeping.

Executive Mode. Maximum signal, zero noise. Bullet points. Priorities. Recommendations. JARVIS speaks like a C-suite advisor — because sometimes that's exactly what you need.

Venting Mode. Sometimes you don't want solutions. You just need to be heard. JARVIS listens. Reflects. Validates. No unsolicited advice. Just presence.

Six personalities. One JARVIS. Always on. Always ready.

Which one do you need first?
""".strip()

out_path = pathlib.Path(__file__).parent / "public" / "audio" / "modes_narration.mp3"
out_path.parent.mkdir(parents=True, exist_ok=True)

print("Generating narration with OpenAI TTS (onyx)...")
with client.audio.speech.with_streaming_response.create(
    model="tts-1",
    voice="onyx",
    input=SCRIPT,
    speed=0.9,
) as response:
    response.stream_to_file(out_path)

size_kb = out_path.stat().st_size // 1024
print(f"Done! Saved to {out_path} ({size_kb} KB)")
