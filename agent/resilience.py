"""Classification and graceful handling of Anthropic API failures.

The Anthropic SDK already retries transient errors (429, 500-range, 529, and
network failures) with exponential backoff and honors `retry-after`;
`config.API_MAX_RETRIES` tunes how many attempts it makes. This module covers
what the SDK does not: turning an error that outlasted every retry into a clear
category and a graceful, user-facing sentence — so a failed turn ends with a
reply instead of an unhandled exception that crashes the caller (an SMS webhook,
a scheduled job, or a dashboard request).
"""
import anthropic


def classify(exc: Exception) -> str:
    """Map an exception to a short category string for logs and messaging."""
    if isinstance(exc, anthropic.RateLimitError):
        return "rate_limit"
    if isinstance(exc, (anthropic.APITimeoutError, anthropic.APIConnectionError)):
        return "network"
    if isinstance(exc, anthropic.APIStatusError):
        status = getattr(exc, "status_code", 0) or 0
        if status == 529:
            return "overloaded"
        if status >= 500:
            return "server_error"
        if status in (401, 403):
            return "auth"
        return "client_error"
    if isinstance(exc, anthropic.APIError):
        return "api_error"
    return "unexpected"


_MESSAGES = {
    "rate_limit": "I'm being rate-limited by the API right now. Give me a moment and try again.",
    "network": "I couldn't reach the API — looks like a network issue. Try again in a moment.",
    "overloaded": "The API is overloaded right now. Try again in a minute.",
    "server_error": "The API had a server error. Try again shortly.",
    "auth": "My API key was rejected — this needs a config fix before I can respond.",
    "client_error": "The API rejected that request as malformed. Let me know how to proceed.",
    "api_error": "I hit an API error and couldn't finish that turn. Try again.",
    "unexpected": "Something went wrong on my end and I couldn't finish that turn.",
}


def friendly_message(exc: Exception) -> str:
    """A short, user-facing sentence describing a turn that failed after retries."""
    return _MESSAGES.get(classify(exc), _MESSAGES["unexpected"])
