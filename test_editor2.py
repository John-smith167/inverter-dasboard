import streamlit as st
import pandas as pd

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"A": 1, "B": 2, "Total": 3}])

st.write("Current df length:", len(st.session_state.df))

edited_df = st.data_editor(
    st.session_state.df, 
    key="my_editor2", 
    num_rows="dynamic"
)

# Calc
edited_df["Total"] = edited_df.get("A", 0) + edited_df.get("B", 0)

# Save
st.session_state.df = edited_df
