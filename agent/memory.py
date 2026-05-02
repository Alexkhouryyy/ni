"""Conversation memory with automatic summarization."""
import anthropic
import config

_SUMMARY_THRESHOLD = 20  # messages before summarizing


class Memory:
    def __init__(self):
        self.messages: list[dict] = []
        self.summary: str = ""

    def add_user(self, content: list | str) -> None:
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: list) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict]:
        return self.messages

    def maybe_summarize(self, client: anthropic.Anthropic) -> None:
        if len(self.messages) < _SUMMARY_THRESHOLD:
            return

        conversation_text = "\n".join(
            f"{m['role'].upper()}: "
            + (m["content"] if isinstance(m["content"], str)
               else " ".join(
                   b.get("text", "[image]") if isinstance(b, dict) else getattr(b, "text", "[block]")
                   for b in m["content"]
               ))
            for m in self.messages
        )

        resp = client.messages.create(
            model=config.PROACTIVE_MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": (
                    "Summarize this conversation in 3-5 sentences, preserving key decisions, "
                    f"context, and facts:\n\n{conversation_text}"
                ),
            }],
        )
        self.summary = resp.content[0].text
        # Keep only the last 4 messages for continuity
        self.messages = self.messages[-4:]

    def context_prefix(self) -> str:
        if self.summary:
            return f"[Earlier conversation summary: {self.summary}]\n\n"
        return ""
