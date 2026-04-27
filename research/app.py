"""Research Mode dashboard — constraint controls, candidate table, scoring view."""
import streamlit as st

st.set_page_config(page_title="LinguistOS — Research", layout="wide")
st.title("LinguistOS — Research Mode")
st.caption("Constraint exploration and pipeline evaluation.")

with st.sidebar:
    st.header("Constraints")
    st.write("Controls go here.")

st.subheader("Candidates")
st.write("Generated sentences and scores will appear here.")
