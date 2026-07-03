import streamlit as st
import streamlit_shadcn_ui as ui

st.set_page_config(
    page_title="QuizLive - Plateforme Instantanée",
    layout="centered",
    initial_sidebar_state="collapsed"
)

if "role" not in st.session_state:
    st.session_state.role = "Participant"

with st.sidebar:
    st.markdown("### 🎯 QuizLive")
    st.markdown("---")
    est_formateur = ui.switch(label="Mode Formateur", key="role_switch")
    nouveau_role = "Formateur" if est_formateur else "Participant"
    if nouveau_role != st.session_state.role:
        st.session_state.role = nouveau_role
        st.rerun()

from views.formateur_view import render_formateur
from views.participant_view import render_participant

if st.session_state.role == "Participant":
    render_participant()
else:
    render_formateur()