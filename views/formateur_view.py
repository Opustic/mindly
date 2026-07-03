import streamlit as st
import streamlit_shadcn_ui as ui
import core.database as db

STATUS_VARIANTS = {
    db.STATUT_BROUILLON: "secondary",
    db.STATUT_ACTIF: "default",
    db.STATUT_TERMINE: "outline",
}

def render_formateur():
    if "active_quiz_id" not in st.session_state:
        st.session_state.active_quiz_id = None

    # Un titre plus discret et élégant
    st.markdown("<h2 style='font-weight: 700; color: #0f172a; margin-bottom: 20px;'>👑 Tableau de bord Formateur</h2>", unsafe_allow_html=True)

    tab_choice = ui.tabs(
        options=["🚀 Sessions Live", "📝 Création de Quiz"],
        default_value="🚀 Sessions Live",
        key="f_tabs",
    )
    st.write("")

    # ------------------------------------------------------------------
    # ONGLET 1 : Sessions Live
    # ------------------------------------------------------------------
    if tab_choice == "🚀 Sessions Live":
        col_list, col_dash = st.columns([1, 2])

        with col_list:
            st.markdown("<p style='font-weight: 600; font-size: 14px; color: #64748b; margin-bottom: 12px;'>📁 QUIZ DISPONIBLES</p>", unsafe_allow_html=True)
            quizzes = db.list_all_quizzes()

            if not quizzes:
                st.caption("Aucun quiz en mémoire Redis pour le moment.")

            for q in quizzes:
                is_active = q["quiz_id"] == st.session_state.active_quiz_id
                label = f"{q['titre']}"
                if ui.button(
                    label,
                    variant="default" if is_active else "outline",
                    key=f"sel_{q['quiz_id']}",
                    use_container_width=True,
                ):
                    st.session_state.active_quiz_id = q["quiz_id"]
                    st.rerun()

        with col_dash:
            st.markdown("<p style='font-weight: 600; font-size: 14px; color: #64748b; margin-bottom: 12px;'>📺 DÉTAILS DE LA SESSION</p>", unsafe_allow_html=True)

            if not st.session_state.active_quiz_id:
                st.caption("Sélectionnez un questionnaire dans la liste de gauche pour l'analyser ou le lancer.")
            else:
                quiz_id = st.session_state.active_quiz_id
                quiz_info = db.get_quiz(quiz_id)

                if not quiz_info:
                    st.caption("Ce quiz n'existe plus.")
                else:
                    variant = STATUS_VARIANTS.get(quiz_info["statut"], "secondary")
                    
                    with ui.card(
                        title=quiz_info["titre"],
                        description=f"ID Système : {quiz_id}",
                        key="dashboard_card",
                    ):
                        st.markdown(f"**{quiz_info['nb_questions']} questions** — `{quiz_info['duree_par_question_secondes']}s` par question")
                        
                        ui.badges(
                            badge_list=[(f"Statut : {quiz_info['statut']}", variant)],
                            key="badge_status",
                        )
                        st.write("")

                        # ── Code de session (Rendu ultra-pro et visible) ──
                        code = quiz_info.get("code") or db.get_quiz_code(quiz_id)
                        if code:
                            st.markdown(
                                f"<div style='background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 15px;'>"
                                f"<span style='color: #64748b; font-size: 12px; font-weight: 600;'>CODE D'ACCÈS ÉTUDIANT</span>"
                                f"<h2 style='margin: 5px 0 0 0; letter-spacing: 2px; color: #0f172a;'>{code}</h2>"
                                f"</div>", 
                                unsafe_allow_html=True
                            )

                        # ── Actions selon le statut ──
                        if quiz_info["statut"] == db.STATUT_BROUILLON:
                            if ui.button("🚀 Lancer le Quiz en Live", key="act_launch", use_container_width=True):
                                db.start_quiz(quiz_id)
                                st.session_state.active_quiz_id = quiz_id
                                st.rerun()

                        elif quiz_info["statut"] == db.STATUT_ACTIF:
                            leaderboard = db.get_classement(quiz_id)

                            st.markdown("##### 🏆 Classement Live")
                            if leaderboard:
                                # Rendu sous forme de mini-cartes épurées alignées au style Shadcn
                                for p in leaderboard:
                                    st.markdown(
                                        f"<div style='display: flex; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid #f1f5f9; font-size: 14px;'>"
                                        f"<span>🥇 <b>Rang #{p['rang']}</b> — {p['pseudo']}</span>"
                                        f"<span style='font-family: monospace; font-weight: 600;'>{p['score']} pts</span>"
                                        f"</div>", 
                                        unsafe_allow_html=True
                                    )
                            else:
                                st.caption("En attente de la première soumission des participants…")
                            st.write("")

                            col_a, col_b = st.columns(2)
                            with col_a:
                                if ui.button("🔄 Actualiser", variant="outline", key="refresh_live", use_container_width=True):
                                    st.rerun()
                            with col_b:
                                if ui.button("🔴 Clôturer la Session", variant="destructive", key="act_stop", use_container_width=True):
                                    db.stop_quiz(quiz_id)
                                    db.compute_and_store_stats(quiz_id)
                                    st.rerun()

                        # ── Affichage des Stats (Si disponible ou si fermé) ──
                        stats = db.get_stats(quiz_id)
                        if stats:
                            st.write("---")
                            st.markdown("##### 📊 Statistiques de performance")
                            col_m1, col_m2 = st.columns(2)
                            with col_m1:
                                st.metric("Score Moyen", f"{stats['score_moyen']} pts")
                            with col_m2:
                                st.metric("Participants", stats['nb_participants'])

                            st.markdown(f"🏆 **Gagnant final :** `{stats['gagnant_pseudo']}` — {stats['gagnant_score']} pts")

                            st.write("")
                            # Cartes de feedback claires et sobres
                            if stats["meilleure_question"]:
                                with ui.card(title="🔥 Point fort du groupe", description=f"{stats['meilleure_question']['texte']} ({stats['meilleure_question']['taux']}% de réussite)", key="card_stat_best"):
                                    pass
                            if stats["moins_bonne_question"]:
                                st.write("")
                                with ui.card(title="⚠️ Notion à revoir", description=f"{stats['moins_bonne_question']['texte']} ({stats['moins_bonne_question']['taux']}% de réussite)", key="card_stat_worst"):
                                    pass

    # ------------------------------------------------------------------
    # ONGLET 2 : Concepteur de Quiz
    # ------------------------------------------------------------------
    else:
        if "design_version" not in st.session_state:
            st.session_state.design_version = 0
        if "design_questions" not in st.session_state:
            st.session_state.design_questions = [{"texte": "", "choix": "", "bonne_reponse": 0}]

        dv = st.session_state.design_version

        with ui.card(
            title="Créer un questionnaire",
            description="Ajoute dynamiquement tes questions (3 à 20 requises).",
            key=f"designer_card_{dv}",
        ):
            titre = ui.input(placeholder="Titre du quiz", key=f"f_title_{dv}")
            
            st.write("")
            slider_val = ui.slider(
                min_value=10,
                max_value=60,
                step=5,
                default_value=[30],
                label="Temps limite par question (secondes)",
                key=f"f_duree_{dv}",
            )
            duree = slider_val[0] if isinstance(slider_val, list) else slider_val

            st.write("---")

            for i, q in enumerate(st.session_state.design_questions):
                st.markdown(f"##### ❓ Question {i + 1}")

                st.session_state.design_questions[i]["texte"] = ui.input(
                    placeholder="Intitulé de la question (Ex: Quelle commande supprime une clé Redis ?)",
                    key=f"f_txt_{dv}_{i}",
                )
                st.write("")
                st.session_state.design_questions[i]["choix"] = ui.input(
                    placeholder="Options séparées par des virgules (Ex: DEL, REMOVE, DROP)",
                    key=f"f_opt_{dv}_{i}",
                )
                st.write("")
                
                # Alignement épuré pour l'index numérique
                st.markdown("<span style='font-size: 13px; color: #64748b;'>Index de la bonne réponse (0 pour la 1ère option, 1 pour la 2ème...)</span>", unsafe_allow_html=True)
                st.session_state.design_questions[i]["bonne_reponse"] = st.number_input(
                    label="Index de la bonne réponse",
                    min_value=0,
                    max_value=10,
                    value=int(q["bonne_reponse"]),
                    key=f"f_ans_{dv}_{i}",
                    label_visibility="collapsed" # Rend l'interface beaucoup plus homogène
                )
                st.write("---")

            col_add, _ = st.columns([1, 2])
            with col_add:
                if ui.button(
                    "➕ Ajouter une question",
                    variant="secondary",
                    key=f"f_add_q_{dv}",
                    use_container_width=True,
                ):
                    st.session_state.design_questions.append(
                        {"texte": "", "choix": "", "bonne_reponse": 0}
                    )
                    st.rerun()

            st.write("")

            if ui.button(
                "💾 Sauvegarder",
                key=f"f_save_{dv}",
                variant="default",
                use_container_width=True,
            ):
                if not titre.strip():
                    st.error("Le titre du quiz est obligatoire.")
                elif not (3 <= len(st.session_state.design_questions) <= 20):
                    st.error(f"Le quiz doit contenir entre 3 et 20 questions (actuellement : {len(st.session_state.design_questions)}).")
                else:
                    payload = []
                    valid = True

                    for idx, q_data in enumerate(st.session_state.design_questions):
                        choix_list = [c.strip() for c in q_data["choix"].split(",") if c.strip()]
                        if not q_data["texte"].strip() or not choix_list:
                            st.error(f"Question {idx + 1} ou ses options sont incomplètes.")
                            valid = False
                            break
                        if not (0 <= int(q_data["bonne_reponse"]) < len(choix_list)):
                            st.error(f"L'index de la bonne réponse pour la question {idx + 1} n'existe pas dans les options fournies.")
                            valid = False
                            break
                        payload.append({
                            "texte": q_data["texte"],
                            "choix": choix_list,
                            "bonne_reponse": int(q_data["bonne_reponse"]),
                        })

                    if valid:
                        with st.spinner("Sauvegarde en cours..."):
                            try:
                                res = db.create_quiz(titre, int(duree), payload)
                                st.toast(f"✅ Quiz créé ! Code : **{res['code']}**")
                                del st.session_state.design_questions
                                st.session_state.design_version += 1
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))