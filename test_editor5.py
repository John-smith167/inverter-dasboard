import streamlit as st
import pandas as pd

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([{"A": 1, "B": 2, "Total": 3}])

def on_change():
    state = st.session_state["my_editor5"]
    df = st.session_state.df.copy()
    
    for idx, changes in state.get("edited_rows", {}).items():
        if idx in df.index:
            for c, v in changes.items():
                df.at[idx, c] = v
                
    added = state.get("added_rows", [])
    if added:
        for new_row in added:
            full_row = {"A": 0, "B": 0, "Total": 0}
            full_row.update(new_row)
            df = pd.concat([df, pd.DataFrame([full_row])], ignore_index=True)
            
    df["Total"] = df.get("A", 0) + df.get("B", 0)
    st.session_state.df = df

st.data_editor(st.session_state.df, key="my_editor5", num_rows="dynamic", on_change=on_change)
st.write("Current len:", len(st.session_state.df))
