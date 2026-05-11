from __future__ import annotations
import streamlit as st

from rag_core.config import settings
from rag_core.generation.answer import answer_question
from rag_core.schemas import QueryResult


st.set_page_config(page_title="engineer-rag", page_icon="📚", layout="wide")


# ---------- sidebar ---------------------------------------------------------

with st.sidebar:
    st.title("engineer-rag")
    st.caption("Curated engineering articles → grounded answers.")

    top_k = st.slider("Top-k chunks", min_value=3, max_value=12, value=6)
    show_chunks = st.toggle("Show retrieved chunks", value=False)

    st.divider()
    st.caption(f"Embed: `{settings.embed_model}`")
    st.caption(f"LLM: `{settings.llm_model}`")
    st.caption(f"Qdrant: `{settings.qdrant_collection}`")

    st.divider()
    if st.button("Clear chat", use_container_width=True):
        st.session_state.history = []
        st.rerun()


# ---------- session state ---------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []  # list[QueryResult]


# ---------- helpers ---------------------------------------------------------

def render_result(result: QueryResult, show_chunks: bool) -> None:
    st.markdown(result.answer)

    if result.citations:
        st.markdown("**Sources**")
        for i, c in enumerate(result.citations, 1):
            label = f"[{i}] {c.title} — `{c.chunk_id}`"
            with st.expander(label):
                if c.source_url:
                    st.markdown(f"[Open original]({c.source_url})")
                st.markdown(f"> {c.snippet}…")

    if show_chunks and result.retrieved:
        with st.expander(f"Retrieved chunks ({len(result.retrieved)})", expanded=False):
            for i, r in enumerate(result.retrieved, 1):
                st.markdown(
                    f"**[{i}] score={r.score:.3f}** · `{r.chunk.chunk_id}` "
                    f"· {r.chunk.token_count} tokens"
                )
                st.markdown(f"```\n{r.chunk.text[:600]}{'…' if len(r.chunk.text) > 600 else ''}\n```")


# ---------- main ------------------------------------------------------------

st.title("Ask your engineering corpus")

for past in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(past.question)
    with st.chat_message("assistant"):
        render_result(past, show_chunks)

question = st.chat_input("Ask a question about your articles…")
if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Searching corpus & generating answer…"):
            result = answer_question(question, top_k=top_k)
        render_result(result, show_chunks)
        st.session_state.history.append(result)
