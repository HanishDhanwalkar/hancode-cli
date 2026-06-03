# Typical local model context windows:
# - Llama 3.2 8B: 8,192 tokens
# - Mistral 7B: 32,768 tokens (but slower)
# - Neural Chat 7B: 8,192 tokens
# We'll assume 8K and leave 20% buffer for safety

CONTEXT_WINDOW_SIZE = 8192
SAFETY_BUFFER_PERCENT = 0.2  # Reserve 20% for response
MAX_USABLE_TOKENS = int(CONTEXT_WINDOW_SIZE * (1 - SAFETY_BUFFER_PERCENT))


class MessageCompressor:
    """Intelligently shrinks conversation history to fit context window."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token count (4 chars ≈ 1 token for English)."""
        return len(text) // 4

    @staticmethod
    def get_messages_size(messages: list[dict]) -> int:
        """Sum of all message token sizes."""
        total = 0
        for msg in messages:
            total += MessageCompressor.estimate_tokens(
                msg.get("content", "") or ""
            )
        return total

    @staticmethod
    def compress_old_messages(messages: list[dict]) -> list[dict]:
        """
        Intelligently reduce old messages to fit within context window.

        Strategy:
        1. KEEP system prompt (always first)
        2. KEEP most recent user+assistant pairs (last 3 turns)
        3. SUMMARIZE or DROP older messages
        4. ADD a summary token if old messages were dropped
        """
        if len(messages) <= 2:
            return messages

        current_size = MessageCompressor.get_messages_size(messages)

        # Already fits? Don't touch it
        if current_size <= MAX_USABLE_TOKENS:
            return messages

        print(
            f"[CONTEXT] ⚠️  Message history ({current_size} tokens) exceeds limit ({MAX_USABLE_TOKENS}).")
        print(f"[CONTEXT] 🗜️  Compressing conversation...\n")

        # Extract system prompt (keep it)
        system_msg = messages[0] if messages and messages[0].get(
            "role") == "system" else None

        # Get non-system messages
        dialogue = messages[1:] if system_msg else messages

        # Keep last 3 exchanges (6 messages: user-assistant pairs)
        keep_recent = min(6, len(dialogue))
        recent_messages = dialogue[-keep_recent:]

        # Old messages that might be dropped
        old_messages = dialogue[:-
                                keep_recent] if keep_recent < len(dialogue) else []

        # If we're still too large, compress recent messages too
        size_with_recent = MessageCompressor.get_messages_size(recent_messages)
        size_with_system = MessageCompressor.estimate_tokens(
            system_msg.get("content", "")) if system_msg else 0
        current = size_with_recent + size_with_system

        if current > MAX_USABLE_TOKENS:
            # Aggressively trim recent messages
            recent_messages = recent_messages[-2:] if len(
                recent_messages) > 2 else recent_messages

        # Build compressed result
        result = []
        if system_msg:
            result.append(system_msg)

        # Add summary of old conversation if needed
        if old_messages:
            summary = MessageCompressor.summarize_old_exchange(old_messages)
            result.append({
                "role": "system",
                "content": f"[Previous context summary]: {summary}"
            })

        result.extend(recent_messages)

        final_size = MessageCompressor.get_messages_size(result)
        print(
            f"[CONTEXT] ✅ Compressed to {final_size} tokens (from {current_size})\n")

        return result

    @staticmethod
    def summarize_old_exchange(messages: list[dict]) -> str:
        """
        Create a brief summary of old messages.
        Format: "User asked X, received response about Y. Then user asked Z..."
        """
        summary_parts = []

        for msg in messages:
            role = msg.get("role", "").upper()
            content = msg.get("content", "")

            if not content:
                continue

            if role == "USER":
                summary_parts.append(f"User: {content}")
            elif role == "ASSISTANT":
                summary_parts.append(f"Assistant: {content}")

        # Join summaries
        summary = " → ".join(summary_parts[:5])  # Keep last 5 exchanges max

        return summary


class ContextAwareClient:
    """Wrapper around AsyncClient that handles context compression automatically."""

    def __init__(self, async_client):
        self.client = async_client
        self.messages = []

    def add_system_prompt(self, system_content: str):
        """Set the system prompt (usually first)."""
        self.messages = [{"role": "system", "content": system_content}]

    def add_message(self, role: str, content: str, tool_calls=None):
        """Add a message to history."""
        msg = {"role": role, "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    async def chat(self, model: str, tools: list = None, options: dict = None):
        """
        Send chat request, auto-compressing history if needed.
        Returns (response, was_compressed).
        """
        # Compress if needed
        compressed_messages = MessageCompressor.compress_old_messages(
            self.messages)
        was_compressed = len(compressed_messages) < len(self.messages)

        # Send request
        response = await self.client.chat(
            model=model,
            messages=compressed_messages,
            tools=tools,
            options=options
        )

        return response, was_compressed

    def get_size_estimate(self) -> int:
        """Get current message history size in tokens."""
        return MessageCompressor.get_messages_size(self.messages)

    def get_info(self) -> dict:
        """Debug info about current context state."""
        return {
            "num_messages": len(self.messages),
            "estimated_tokens": self.get_size_estimate(),
            "context_limit": MAX_USABLE_TOKENS,
            "utilization_percent": (self.get_size_estimate() / MAX_USABLE_TOKENS) * 100
        }


# ==========================================
# ALTERNATIVE: SELECTIVE MEMORY STRATEGY
# ==========================================

class SelectiveMemory:
    """
    Only keep important messages. Useful when you have many turns.

    Strategy:
    - ALWAYS keep: system prompt
    - ALWAYS keep: last N turns (e.g., 3)
    - SELECTIVELY keep: turns that have tool results or important info
    - DROP: turns with only chitchat
    """

    @staticmethod
    def importance_score(message: dict) -> float:
        """
        Score a message's importance (0.0 to 1.0).
        Higher = more important to keep.
        """
        role = message.get("role", "")
        content = message.get("content", "")

        score = 0.0

        # Tool-related messages are critical
        if message.get("tool_calls"):
            score += 0.9
        if "tool" in content.lower():
            score += 0.5

        # System messages
        if role == "system":
            score += 0.95

        # Long responses (more info)
        if len(content) > 500:
            score += 0.2

        # Results/answers
        if "result" in content.lower() or "answer" in content.lower():
            score += 0.4

        return min(score, 1.0)

    @staticmethod
    def keep_important_messages(
        messages: list[dict],
        keep_recent_turns: int = 3
    ) -> list[dict]:
        """
        Keep only important messages + recent turns.

        Args:
            messages: Full message history
            keep_recent_turns: Number of recent user-assistant pairs to keep
        """
        if len(messages) <= 2:
            return messages

        # Always keep system message
        result = []
        if messages and messages[0].get("role") == "system":
            result.append(messages[0])
            dialogue = messages[1:]
        else:
            dialogue = messages

        # Keep last N turns (user-assistant pairs)
        num_pairs = keep_recent_turns
        keep_count = min(num_pairs * 2, len(dialogue))
        recent = dialogue[-keep_count:] if keep_count > 0 else []

        # From older messages, keep only high-importance ones
        old = dialogue[:-keep_count] if keep_count < len(dialogue) else []
        important_old = [
            msg for msg in old
            if SelectiveMemory.importance_score(msg) > 0.5
        ]

        result.extend(important_old)
        result.extend(recent)

        return result


# ==========================================
# SUMMARIZATION SERVICE (For Long Contexts)
# ==========================================

class ConversationSummarizer:
    """
    For truly long conversations, create a summary from Ollama itself.
    (Requires calling the model once to summarize)
    """

    @staticmethod
    async def summarize_conversation(client, messages: list[dict]) -> str:
        """
        Ask the model to summarize the conversation so far.
        Use this summary as a system message to "reset" context.
        """
        dialogue_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content'][:300]}"
            for msg in messages[1:]  # Skip system prompt
        ])

        summary_prompt = (
            "Summarize this conversation in 2-3 sentences, focusing on:\n"
            "- What the user asked\n"
            "- What was discovered/solved\n"
            "- Any important context for future responses\n\n"
            f"{dialogue_text}"
        )

        response = await client.chat(
            model="llama2",  # Adjust to your model
            messages=[{"role": "user", "content": summary_prompt}],
            options={"temperature": 0.3}
        )

        return response.message.content
