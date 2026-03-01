import streamlit as st
import pandas as pd

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"A": 1, "B": 2, "Total": 3}])

edited_df = st.data_editor(st.session_state.df, key="editor6", num_rows="dynamic")

# Check if changed
if not edited_df.equals(st.session_state.df):
    edited_df["Total"] = edited_df.get("A", 0) + edited_df.get("B", 0)
    st.session_state.df = edited_df
    st.rerun()

st.write("DF Length:", len(st.session_state.df))
