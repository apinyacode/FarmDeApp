"""Step 3: side-by-side review app. The scan is on the left, the editable text on the right.

Usage:
    streamlit run step3_review_app.py

Your browser opens at http://localhost:8501. Edits are saved to
work/<pdf name>/reviewed/, never on top of Claude's original in ai/.
"""

import html
import time

import pandas as pd
import streamlit as st

from common import (
    UNSURE_PATTERN,
    best_version,
    list_documents,
    list_pages,
    read_json,
    unsure_words,
    work_dir_for,
    write_json,
)

STATUS_LABELS = {
    "approved": "✅ Approved",
    "needs_check": "🟡 Needs check",
    "ai_only": "🤖 Not reviewed yet",
    "not_transcribed": "⬜ Not transcribed",
}
FILTERS = {
    "Everything not approved": lambda status, data: status != "approved",
    "Low/medium confidence first": lambda status, data: status != "approved"
    and data is not None and data.get("confidence") in ("low", "medium"),
    "Approved": lambda status, data: status == "approved",
    "All pages": lambda status, data: True,
}

st.set_page_config(page_title="Thai handwriting review", layout="wide")
st.markdown(
    """<style>
    .line-preview { font-size: 1.15rem; line-height: 1.9; }
    .line-no { color: #888; display: inline-block; width: 2.2em; }
    mark { background: #ffe066; padding: 0 2px; border-radius: 3px; }
    .fixed { text-decoration: underline 3px #2f9e44; text-underline-offset: 5px; cursor: help; }
    /* Keep the scan on screen while you scroll down through the text boxes. */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stTabs"]) > div[data-testid="stColumn"]:first-child {
        position: sticky; top: 3.5rem; align-self: flex-start;
    }
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stTabs"]) > div[data-testid="stColumn"]:first-child img {
        max-height: calc(100vh - 9rem); object-fit: contain;
    }
    </style>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- sidebar
documents = list_documents()
if not documents:
    st.error("No documents yet. Run step1_extract_pages.py first.")
    st.stop()

with st.sidebar:
    document = st.selectbox("Document", documents)
    doc_dir = work_dir_for(document)
    all_pages = list_pages(doc_dir)
    statuses = {page: best_version(doc_dir, page) for page in all_pages}

    approved = sum(1 for _, status in statuses.values() if status == "approved")
    st.progress(approved / len(all_pages), text=f"{approved} of {len(all_pages)} pages approved")

    filter_name = st.radio("Show", list(FILTERS))
    keep = FILTERS[filter_name]
    pages = [p for p in all_pages if keep(statuses[p][1], statuses[p][0])]
    if not pages:
        st.success("Nothing left in this list 🎉")
        st.stop()

    # Remember which page we're on, separately for each filter.
    position_key = f"position::{document}::{filter_name}"
    st.session_state.setdefault(position_key, 0)
    st.session_state[position_key] = min(st.session_state[position_key], len(pages) - 1)

    chosen = st.selectbox(
        "Page",
        range(len(pages)),
        index=st.session_state[position_key],
        format_func=lambda i: f"{pages[i]}  {STATUS_LABELS[statuses[pages[i]][1]]}",
    )
    st.session_state[position_key] = chosen

    reviewer = st.text_input("Your name (saved with each review)", key="reviewer")
    st.caption("Tip: hover over the scan and click ⛶ to see it full screen.")


def go(step: int) -> None:
    st.session_state[position_key] = max(0, min(len(pages) - 1, st.session_state[position_key] + step))


page = pages[st.session_state[position_key]]
data, status = statuses[page]
data = data or {}
ai_version = read_json(doc_dir / "ai" / f"{page}.json")

# ---------------------------------------------------------------- main area
st.subheader(f"{document} · {page}   {STATUS_LABELS[status]}")
left, right = st.columns([1, 1], gap="large")

with left:
    crop_tab, full_tab = st.tabs(["Handwriting (crop)", "Full page"])
    with crop_tab:
        st.image(str(doc_dir / "crops" / f"{page}.jpg"), width="stretch")
    with full_tab:
        st.image(str(doc_dir / "pages" / f"{page}.jpg"), width="stretch")

with right:
    lines = data.get("lines", [])
    corrections = data.get("corrections", [])
    flags = unsure_words(lines)
    info = [f"Confidence: **{data.get('confidence', '–')}**"]
    if flags:
        info.append(f"Unsure words: **{len(flags)}** (yellow)")
    if corrections:
        info.append(f"Spelling fixes: **{len(corrections)}** (green underline)")
    if data.get("continues_from_previous"):
        info.append("↩️ continues from previous page")
    if data.get("continues_to_next"):
        info.append("↪️ continues on next page")
    st.markdown(" · ".join(info))

    # Numbered, highlighted copy of the lines, to compare against the scan line by line.
    with st.expander("Line-by-line preview (hover a green word to see how it was written)", expanded=True):
        rows = []
        for number, line in enumerate(lines, start=1):
            marked = UNSURE_PATTERN.sub(lambda m: f"<mark>{m.group(1)}</mark>", html.escape(line))
            for fix in corrections:
                if fix.get("line") == number and fix.get("corrected"):
                    word = html.escape(fix["corrected"])
                    tip = html.escape(f"written: {fix.get('as_written', '')}", quote=True)
                    marked = marked.replace(word, f"<span class='fixed' title='{tip}'>{word}</span>", 1)
            rows.append(f"<span class='line-no'>{number}</span>{marked}")
        st.markdown(f"<div class='line-preview'>{'<br>'.join(rows) or '<i>(empty)</i>'}</div>",
                    unsafe_allow_html=True)

    # Each widget key includes the page name so the boxes refill when you change page.
    edited_lines = st.text_area(
        "Lines, same line breaks as the paper, spelling corrected. Remove the ⟦ ⟧ marks once a word is checked.",
        "\n".join(lines), height=300, key=f"lines::{document}::{page}",
    )
    st.markdown("**Spelling fixes** (edit or delete a row if the fix is wrong; also change the line above)")
    edited_fixes = st.data_editor(
        pd.DataFrame(corrections, columns=["line", "as_written", "corrected"]),
        column_config={
            "line": st.column_config.NumberColumn("Line", min_value=1, step=1, width="small"),
            "as_written": st.column_config.TextColumn("As written"),
            "corrected": st.column_config.TextColumn("Corrected"),
        },
        column_order=["line", "as_written", "corrected"],
        num_rows="dynamic", hide_index=True, width="stretch", key=f"fixes::{document}::{page}",
    )
    greeting = st.text_input("Greeting", data.get("greeting", ""), key=f"greeting::{document}::{page}")
    question = st.text_area("Question (clean version)", data.get("question", ""), height=160,
                            key=f"question::{document}::{page}")
    closing = st.text_input("Closing", data.get("closing", ""), key=f"closing::{document}::{page}")
    notes = st.text_area("Notes", data.get("notes", ""), height=80, key=f"notes::{document}::{page}")
    col_a, col_b = st.columns(2)
    from_prev = col_a.checkbox("Continues from previous page", data.get("continues_from_previous", False),
                               key=f"prev::{document}::{page}")
    to_next = col_b.checkbox("Continues on next page", data.get("continues_to_next", False),
                             key=f"next::{document}::{page}")

    def save(new_status: str) -> None:
        new_lines = [line.rstrip() for line in edited_lines.splitlines()]
        write_json(doc_dir / "reviewed" / f"{page}.json", {
            "lines": new_lines,
            "corrections": [
                {"line": int(fix["line"]) if fix["line"] != "" else None,
                 "as_written": str(fix["as_written"] or "").strip(),
                 "corrected": str(fix["corrected"] or "").strip()}
                for fix in edited_fixes.fillna("").to_dict("records")
                if fix["as_written"] or fix["corrected"]
            ],
            "greeting": greeting.strip(),
            "question": question.strip(),
            "closing": closing.strip(),
            "notes": notes.strip(),
            "continues_from_previous": from_prev,
            "continues_to_next": to_next,
            "confidence": data.get("confidence", ""),
            "status": new_status,
            "reviewed_by": reviewer.strip(),
            "reviewed_at": time.strftime("%Y-%m-%d %H:%M"),
        })

    remaining = unsure_words(edited_lines.splitlines())
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("✅ Approve", type="primary", width="stretch"):
        save("approved")
        # If approved pages are hidden by the filter, this page drops out of the list
        # and the next one slides into its place, so only move on when it stays visible.
        if keep("approved", data):
            go(+1)
        st.rerun()
    if b2.button("💾 Later", width="stretch"):
        save("needs_check")
        st.toast(f"Saved {page}")
        st.rerun()
    b3.button("◀ Prev", on_click=go, args=(-1,), width="stretch")
    b4.button("Next ▶", on_click=go, args=(+1,), width="stretch")

    if remaining:
        st.caption(f"⚠️ Still {len(remaining)} ⟦unsure⟧ mark(s) in the lines. You can approve anyway "
                   "if you checked them and left the marks on purpose.")
    if ai_version and status in ("approved", "needs_check"):
        with st.expander("Compare with Claude's original"):
            st.text("\n".join(ai_version.get("lines", [])))
