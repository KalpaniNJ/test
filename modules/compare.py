import streamlit as st
import streamlit.components.v1 as components

SEASONS = ["Maha 2023/24", "Yala 2024", "Maha 2024/25"]

def _split_screen_html(left_label: str, right_label: str, height_px: int = 520) -> str:
    # ... HTML content here (the long code I gave earlier) ...
    return """<!doctype html> ... """

def show(params=None):   # ✅ make params optional
    st.title("🌾 Simple Split Screen (No Computation)")

    c1, c2 = st.columns(2)
    with c1:
        left_label = st.selectbox("Left label", SEASONS, index=0, key="left_label")
    with c2:
        right_label = st.selectbox("Right label", SEASONS, index=1, key="right_label")

    if st.button("Run Comparison"):
        st.success(f"Showing: {left_label} vs {right_label}")
        html_doc = _split_screen_html(left_label, right_label, height_px=520)
        components.html(html_doc, height=540)
    else:
        st.info("Select labels and click **Run Comparison** to show the split screen.")
