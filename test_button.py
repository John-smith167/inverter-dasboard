
import streamlit as st

st.write("Testing button width")
try:
    st.button("Test Button", width="stretch")
    st.write("✅ Button created with width='stretch'")
except Exception as e:
    st.write(f"❌ Error: {e}")
