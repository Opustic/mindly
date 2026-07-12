import os
import streamlit as st
import streamlit_shadcn_ui as ui
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Mindly",
    layout="centered",
    initial_sidebar_state="collapsed"
)

FORMATEUR_PASSWORD = os.environ.get("FORMATEUR_PASSWORD", "admin")

if "role" not in st.session_state:
    st.session_state.role = "Participant"

with st.sidebar:
    st.markdown("### 🎯 Mindly")
    st.markdown("---")
    est_formateur = ui.switch(label="Mode Formateur", key="role_switch")

    if est_formateur:
        if "formateur_auth" not in st.session_state:
            st.session_state.formateur_auth = False

        if not st.session_state.formateur_auth:
            pwd = st.text_input("Mot de passe", type="password", key="pwd_input")
            if st.button("Accéder", key="btn_auth"):
                if pwd == FORMATEUR_PASSWORD:
                    st.session_state.formateur_auth = True
                    st.session_state.role = "Formateur"
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect")
        else:
            st.caption("✅ Mode Formateur actif")
            if st.button("Déconnexion", key="btn_logout"):
                st.session_state.formateur_auth = False
                st.session_state.role = "Participant"
                st.rerun()
    else:
        st.session_state.formateur_auth = False

from views.formateur_view import render_formateur
from views.participant_view import render_participant

if st.session_state.role == "Participant":
    render_participant()
else:
    if not st.session_state.get("formateur_auth"):
        st.session_state.role = "Participant"
        st.rerun()
    render_formateur()