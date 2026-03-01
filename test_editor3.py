import streamlit as st
import pandas as pd

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"A": 1}])

def on_change():
    state = st.session_state["my_editor3"]
    print("State type:", type(state))
    print("State:", state)

st.data_editor(st.session_state.df, key="my_editor3", on_change=on_change, num_rows="dynamic")
