import streamlit as st
import streamlit_shadcn_ui as ui
import core.database as db

def render_participant():
    if "p_step" not in st.session_state:
        st.session_state.p_step = "connexion"
    if "st_quiz_id" not in st.session_state:
        st.session_state.st_quiz_id = None
    if "pseudo" not in st.session_state:
        st.session_state.pseudo = ""
    if "current_q_idx" not in st.session_state:
        st.session_state.current_q_idx = 0
    if "last_result" not in st.session_state:
        st.session_state.last_result = None

    # ------------------------------------------------------------------
    # ÉTAPE 1 : CONNEXION
    # ------------------------------------------------------------------
    if st.session_state.p_step == "connexion":
        st.write("")

        with ui.card(
            title="🎮 Rejoindre une session",
            description="Entre le code fourni par ton formateur pour commencer.",
            key="join_card",
        ):
            code_input = ui.input_otp(max_length=6, key="code_otp") or ""
            pseudo_input = ui.input(placeholder="Ton pseudo", key="pseudo_input") or ""

            st.write("")

            if ui.button("Valider et Entrer", variant="default", key="btn_join", use_container_width=True):
                code = code_input.strip().upper()
                pseudo = pseudo_input.strip()
                if not code or not pseudo:
                    st.error("Tous les champs sont obligatoires.")
                else:
                    quiz_id = db.get_quiz_id_from_code(code)
                    if not quiz_id:
                        st.error("Code invalide ou expiré.")
                    else:
                        try:
                            db.join_quiz(quiz_id, pseudo)
                            st.session_state.st_quiz_id = quiz_id
                            st.session_state.pseudo = pseudo
                            st.session_state.p_step = "jeu"
                            st.session_state.current_q_idx = 0
                            st.session_state.last_result = None
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

    # ------------------------------------------------------------------
    # ÉTAPE 2 : JEU
    # ------------------------------------------------------------------
    elif st.session_state.p_step == "jeu":
        quiz = db.get_quiz(st.session_state.st_quiz_id)
        if not quiz or quiz["statut"] == db.STATUT_TERMINE:
            st.session_state.p_step = "fin"
            st.rerun()

        st.subheader(f"📖 {quiz['titre']}")
        ui.badges(badge_list=[(f"Joueur : {st.session_state.pseudo}", "secondary")], key="badge_player")
        st.write("")

        questions = quiz["questions"]
        q_idx = st.session_state.current_q_idx

        if questions:
            ui.progress(data=int(q_idx / len(questions) * 100), key="progress_quiz")

        if q_idx < len(questions):
            question = questions[q_idx]
            deja_repondu = db.has_answered(st.session_state.st_quiz_id, q_idx, st.session_state.pseudo)

            with ui.card(
                title=f"Question {q_idx + 1} / {len(questions)}",
                key=f"q_card_{q_idx}",
            ):
                st.markdown(f"**{question['texte']}**")
                st.write("")
                if deja_repondu:
                    result = st.session_state.last_result
                    if result:
                        if result.get("correct"):
                            ui.alert(
                                title="✅ Bonne réponse !",
                                description=f"+{result['points_gagnes']} points  —  Score total : {result['score_total']}",
                                key=f"alert_ok_{q_idx}",
                            )
                        else:
                            ui.alert(
                                title="❌ Mauvaise réponse",
                                description="Ne lâche rien, la prochaine est pour toi !",
                                key=f"alert_ko_{q_idx}",
                            )
                    else:
                        ui.badges(badge_list=[("Réponse enregistrée ✓", "outline")], key=f"badge_done_{q_idx}")

                    if ui.button("Question Suivante ➡️", variant="secondary", key=f"next_{q_idx}", use_container_width=True):
                        st.session_state.current_q_idx += 1
                        st.session_state.last_result = None
                        st.rerun()

                else:
                    choix = st.radio("Choix :", question["choix"], index=None, label_visibility="collapsed")
                    st.write("")

                    if ui.button("Soumettre ma réponse", key=f"sub_{q_idx}", disabled=choix is None):
                        reponse_idx = question["choix"].index(choix)
                        res = db.submit_answer(
                            quiz_id=st.session_state.st_quiz_id,
                            q_idx=q_idx,
                            pseudo=st.session_state.pseudo,
                            reponse_idx=reponse_idx,
                            temps_restant_secondes=float(quiz["duree_par_question_secondes"]),
                        )
                        if res["accepte"]:
                            st.session_state.last_result = res
                            st.rerun()
                        else:
                            st.error(f"Erreur : {res['raison']}")
        else:
            st.session_state.p_step = "fin"
            st.rerun()

    # ------------------------------------------------------------------
    # ÉTAPE 3 : FIN
    # ------------------------------------------------------------------
    elif st.session_state.p_step == "fin":
        with ui.card(
            title="🏁 Session Terminée !",
            description="Tu as complété le questionnaire.",
            key="fin_card",
        ):
            st.write("Regarde l'écran du formateur pour découvrir le classement final complet.")
            st.write("")
            if ui.button("Quitter", variant="destructive", key="btn_exit_p"):
                st.session_state.clear()
                st.rerun()
