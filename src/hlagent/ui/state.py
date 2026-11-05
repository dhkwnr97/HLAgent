"""Per-browser-session state: keys typed in the GUI (memory only), the ChatSession and chat transcript."""

from __future__ import annotations

from typing import Any

import streamlit as st

from hlagent.agents.session import ChatSession, Reply
from hlagent.config import get_settings
from hlagent.llm.registry import Keys
from hlagent.ui.bridge import AsyncBridge

KEY_FIELDS = {
    "google": "Google (Gemini)",
    "openai": "OpenAI",
    "anthropic": "Anthropic (Claude)",
    "tavily": "Tavily (web search)",
    "typesafe": "TypeSafe (Jev router)",
}


@st.cache_resource
def bridge() -> AsyncBridge:
    return AsyncBridge()


def key_overrides() -> dict[str, str]:
    return st.session_state.setdefault("key_overrides", {})


def keys() -> Keys:
    return Keys.resolve(get_settings(), key_overrides())


def session() -> ChatSession:
    """The chat session, rebuilt (history kept) when keys, provider or mode change."""
    sig = (
        st.session_state.get("keys_version", 0),
        st.session_state.get("provider"),
        st.session_state.get("mode", "auto"),
    )
    s: ChatSession | None = st.session_state.get("chat_session")
    if s is None:
        s = ChatSession(
            keys=keys(), provider=st.session_state.get("provider"), mode=st.session_state.get("mode", "auto")
        )
        st.session_state["chat_session"] = s
    elif st.session_state.get("chat_sig") != sig:
        s.keys, s.provider, s.mode = (
            keys(),
            st.session_state.get("provider"),
            st.session_state.get("mode", "auto"),
        )
        s._models, s._kb = {}, None
    st.session_state["chat_sig"] = sig
    return s


def transcript() -> list[dict[str, Any]]:
    return st.session_state.setdefault("messages", [])


def add_user(text: str) -> None:
    transcript().append({"role": "user", "kind": "text", "content": text, "data": {}})


def add_replies(replies: list[Reply]) -> None:
    for r in replies:
        transcript().append({"role": "assistant", "kind": r.kind, "content": r.content, "data": r.data})
