import os
import base64
import streamlit as st
import pandas as pd
from utils.config import AOI_OPTIONS


def load_logo_as_base64(path):
    """Convert a local image file to base64 so it can be embedded in HTML."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def sidebar_controls():
    st.sidebar.header("Dashboard Controls")


