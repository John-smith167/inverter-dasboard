import streamlit as st
import pandas as pd

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"A": 1, "B": 2, "Total": 3}])

def on_change():
    state = st.session_state["my_editor"]
    
    # manual patch
    df = st.session_state.df.copy()
    for idx, changes in state.get("edited_rows", {}).items():
        if idx in df.index:
            for c, v in changes.items():
                df.at[idx, c] = v
    for new_row in state.get("added_rows", []):
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    
    # calc
    df["Total"] = df.get("A", 0) + df.get("B", 0)
    st.session_state.df = df
    print("on_change fired. df is now:", len(df))

st.data_editor(st.session_state.df, key="my_editor", on_change=on_change, num_rows="dynamic")
