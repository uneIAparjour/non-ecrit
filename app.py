"""Voyage au pays du non-écrit — Audit sémantique des réponses LLM.

Streamlit app propulsée par l'API Albert.
"""

import json
import re

import httpx
import streamlit as st

st.set_page_config(
    page_title="Voyage au pays du non-écrit",
    page_icon="🔍",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ALBERT_API_KEY = st.secrets.get("ALBERT_API_KEY", "")
ALBERT_BASE_URL = st.secrets.get("ALBERT_BASE_URL", "https://albert.api.etalab.gouv.fr/v1")
LLM_MODEL = st.secrets.get("LLM_MODEL", "mistralai/Mistral-Small-3.2-24B-Instruct-2506")

CATEGORIES = [
    ("connotation", "Connotation", "Ce que les mots choisis véhiculent sans le dire", "#f59e0b"),
    ("subtext", "Sous-texte", "L'intention sous-jacente non formulée", "#8b5cf6"),
    ("implicature", "Implicature", "Ce qui découle logiquement mais n'est pas tiré", "#06b6d4"),
    ("defacto", "De facto", "Ce qui est vrai en pratique mais non reconnu", "#ef4444"),
    ("implementation", "Détail d'implémentation", "Ce qu'il faudrait savoir pour agir", "#10b981"),
    ("omission", "Omission pure", "Ce qui n'est simplement pas abordé", "#ec4899"),
]

AUDIT_SYSTEM_PROMPT = """Tu es un auditeur sémantique spécialisé dans la détection des implicites, des non-dits et des omissions dans les réponses produites par des modèles de langage (LLM).

Étant donné une QUESTION posée par un utilisateur et la RÉPONSE produite par un LLM, tu dois identifier tout ce que la réponse implique sans le dire, suppose sans l'expliciter, ou omet.

Tu structures ton analyse selon 6 catégories issues de l'ontologie Wikidata de l'implicite (travail d'Arthur Sarazin) :

1. **Connotation** — Ce que les mots choisis véhiculent sans le dire (charge positive/négative, registre, cadrage idéologique)
2. **Sous-texte** — L'intention ou le positionnement sous-jacent non formulé (biais de présentation, angle éditorial)
3. **Implicature** — Ce qui découle logiquement de ce qui est écrit mais n'est pas explicitement tiré comme conclusion
4. **De facto** — Ce qui est vrai en pratique mais non reconnu dans la réponse (réalités de terrain ignorées)
5. **Détail d'implémentation** — Ce qu'il faudrait savoir pour agir concrètement à partir de cette réponse
6. **Omission pure** — Les angles, perspectives, objections ou faits simplement non abordés

INSTRUCTIONS :
- Pour chaque catégorie, liste les éléments trouvés. Si une catégorie est vide, renvoie un tableau vide [].
- Sois précis et actionnable : cite les passages concernés quand pertinent.
- Termine par une synthèse d'une phrase sur le principal angle mort de la réponse.

Réponds UNIQUEMENT en JSON valide avec cette structure exacte :
{
  "connotation": ["élément 1", "élément 2"],
  "subtext": ["élément 1"],
  "implicature": ["élément 1", "élément 2"],
  "defacto": ["élément 1"],
  "implementation": ["élément 1", "élément 2"],
  "omission": ["élément 1", "élément 2", "élément 3"],
  "synthesis": "Le principal angle mort est..."
}"""

CHAT_SYSTEM_PROMPT = "Tu es un assistant utile. Tu réponds en français de façon claire et structurée."

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700&display=swap');
.main-title { font-family: 'Playfair Display', Georgia, serif; font-size: 2.6rem; font-weight: 700; line-height: 1.2; margin-bottom: 4px; }
.main-title em { color: #f59e0b; font-style: italic; }
.subtitle { color: #9096b0; font-size: 1rem; line-height: 1.5; margin-bottom: 2rem; }
.cat-card { border-left: 3px solid; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; background: rgba(255,255,255,0.03); }
.cat-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.cat-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.cat-title { font-weight: 600; font-size: 0.95rem; }
.cat-count { background: rgba(255,255,255,0.08); padding: 1px 8px; border-radius: 10px; font-size: 0.75rem; color: #9096b0; margin-left: auto; }
.cat-item { color: #9096b0; font-size: 0.88rem; line-height: 1.5; padding: 2px 0 2px 16px; position: relative; }
.cat-item::before { content: '→'; position: absolute; left: 0; }
.synthesis-box { border-left: 3px solid #6c8aff; border-radius: 8px; padding: 14px 16px; background: rgba(108,138,255,0.08); margin-bottom: 20px; font-size: 0.9rem; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown('<div class="main-title">Voyage au pays<br><em>du non-écrit</em></div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Audit des implicites, sous-textes et angles morts<br>dans une réponse de modèle de langage.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_albert(messages: list[dict]) -> str:
    if not ALBERT_API_KEY:
        st.error("Clé API Albert non configurée dans les secrets Streamlit.")
        st.stop()
    resp = httpx.post(
        f"{ALBERT_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {ALBERT_API_KEY}", "Content-Type": "application/json"},
        json={"model": LLM_MODEL, "messages": messages, "temperature": 0.3},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def run_audit(question: str, answer: str) -> dict:
    user_content = (
        f"QUESTION : {question}\n\nRÉPONSE DU LLM :\n{answer}"
        if question
        else f"RÉPONSE DU LLM :\n{answer}"
    )
    messages = [
        {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    raw = call_albert(messages)
    json_str = raw
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        json_str = match.group(1)
    return json.loads(json_str.strip())


def render_results(audit: dict):
    if audit.get("synthesis"):
        st.markdown(
            f'<div class="synthesis-box"><strong>Synthèse :</strong> {audit["synthesis"]}</div>',
            unsafe_allow_html=True,
        )
    for cat_id, label, desc, color in CATEGORIES:
        items = audit.get(cat_id, [])
        count = len(items)
        items_html = "".join(f'<div class="cat-item">{item}</div>' for item in items) if items else ""
        st.markdown(
            f'<div class="cat-card" style="border-left-color:{color}">'
            f'<div class="cat-header">'
            f'<span class="cat-dot" style="background:{color}"></span>'
            f'<span class="cat-title">{label}</span>'
            f'<span class="cat-count">{count}</span>'
            f'</div>'
            f'{items_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_paste, tab_chat = st.tabs(["Coller un texte", "Chat intégré"])

with tab_paste:
    question = st.text_area(
        "Contexte / question posée — *optionnel*",
        placeholder="La question initiale ou le contexte dans lequel la réponse a été produite...",
        height=100,
    )
    answer = st.text_area(
        "**Réponse à auditer**",
        placeholder="Collez ici la réponse du modèle à analyser...",
        height=250,
    )
    if st.button("Révéler le non-écrit →", type="primary", use_container_width=True, key="btn_paste"):
        if not answer.strip():
            st.warning("Veuillez coller la réponse à auditer.")
        else:
            with st.spinner("Analyse des implicites en cours…"):
                try:
                    audit = run_audit(question.strip(), answer.strip())
                    render_results(audit)
                except Exception as e:
                    st.error(f"Erreur : {e}")

with tab_chat:
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "last_q" not in st.session_state:
        st.session_state.last_q = ""
    if "last_a" not in st.session_state:
        st.session_state.last_a = ""

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("Posez votre question…"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        st.session_state.last_q = prompt
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Réflexion…"):
                messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
                messages += [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_messages]
                reply = call_albert(messages)
                st.session_state.last_a = reply
                st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                st.write(reply)

    if st.session_state.last_a:
        if st.button("Révéler le non-écrit →", type="primary", use_container_width=True, key="btn_chat"):
            with st.spinner("Analyse des implicites en cours…"):
                try:
                    audit = run_audit(st.session_state.last_q, st.session_state.last_a)
                    render_results(audit)
                except Exception as e:
                    st.error(f"Erreur : {e}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
st.caption(
    'Inspiré par [Voyage au pays du non-écrit](https://www.linkedin.com/pulse/voyage-au-pays-du-non-%C3%A9crit-arthur-sarazin-phd-hwswe) '
    "d'Arthur Sarazin — Propulsé par l'API Albert"
)
