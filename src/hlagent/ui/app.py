"""Streamlit entry point: `hlagent ui` or `streamlit run src/hlagent/ui/app.py`."""

from __future__ import annotations

import streamlit as st

from hlagent.ui import pages

st.set_page_config(page_title="HLAgent v3", page_icon="🧬", layout="wide")

nav = st.navigation(
    [
        st.Page(pages.chat_page, title="Chat", icon=":material/chat:", url_path="chat", default=True),
        st.Page(pages.results_page, title="Results", icon=":material/analytics:", url_path="results"),
        st.Page(pages.data_page, title="Data", icon=":material/folder:", url_path="data"),
        st.Page(
            pages.knowledge_page, title="Knowledge base", icon=":material/menu_book:", url_path="knowledge"
        ),
        st.Page(pages.settings_page, title="Settings", icon=":material/settings:", url_path="settings"),
    ]
)
nav.run()
