"""
Generate narration audio v2 for JARVIS Study Mode trailer using OpenAI TTS.
120 seconds / ~240 words — speaks slowly and clearly.
"""

import os
from pathlib import Path
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

NARRATION = (
    "In school, you learn by asking questions and getting answers. "
    "But real learning — deep understanding — comes from the struggle. "
    "JARVIS now has a mode that changes everything. Study Mode. "
    "When activated, JARVIS transforms from a fast answer machine into a Socratic tutor. "
    "He will not give you direct answers to learning questions. "
    "He turns every question back on you. "
    "Ask him what recursion is. He says: Before I explain — what do you think it might mean? "
    "Try the shortcut. Tell him: just give me the answer. "
    "He says: Not in study mode, sir. Work through it. "
    "Study Mode works for any subject you want to master. "
    "Learning to code? Ask about closures. He won't explain them. He makes you discover them. "
    "You have used setTimeout in a loop. What did it print — and why? "
    "Studying maths? Ask why zero factorial equals one. "
    "He responds: What is the formula for n factorial in terms of n minus one factorial? Now set n to one and solve. "
    "Even history. Why did Rome fall? "
    "He asks: Which theory interests you most — military, economic, or political? Pick one and defend it. "
    "Every subject. Every level. Socratic method on demand. "
    "When your session ends, toggle Study Mode off. "
    "JARVIS delivers a summary. What you covered. Where you are strong. What needs review. "
    "Knowing the answer is not the same as understanding it. "
    "JARVIS. Study Mode. The teacher you always needed."
)

OUTPUT_DIR = Path(__file__).parent / "public" / "audio"
OUTPUT_FILE = OUTPUT_DIR / "narration.mp3"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")

    client = OpenAI(api_key=OPENAI_API_KEY)

    print("Calling OpenAI TTS API (voice: onyx, model: tts-1)...")
    response = client.audio.speech.create(
        model="tts-1",
        voice="onyx",
        input=NARRATION,
        response_format="mp3",
    )

    response.stream_to_file(OUTPUT_FILE)

    size = OUTPUT_FILE.stat().st_size
    print(f"Saved to: {OUTPUT_FILE}")
    print(f"File size: {size:,} bytes ({size / 1024:.1f} KB)")

    if size < 150_000:
        print("WARNING: File size is less than 150KB — may be truncated!")
    else:
        print("OK: File size looks good.")


if __name__ == "__main__":
    main()
