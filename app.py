"""Voyage au pays du non-écrit — Audit sémantique des réponses LLM.

Streamlit app propulsée par l'API Albert.
"""

import html
import json
import os
import re
import time
from pathlib import Path

import httpx
import streamlit as st
import streamlit.components.v1 as components

if "lang" not in st.session_state:
    st.session_state["lang"] = "en" if st.query_params.get("lang") == "en" else "fr"
LANG = st.session_state["lang"]

st.set_page_config(
    page_title="Voyage au pays du non-écrit" if LANG == "fr" else "The Unwritten Journey",
    page_icon="◇",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _config(key: str, default: str = "") -> str:
    """Read config from Streamlit secrets (Streamlit Cloud) or the environment
    (Render and other hosts without a secrets.toml file)."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


ALBERT_API_KEY = _config("ALBERT_API_KEY")
ALBERT_BASE_URL = _config("ALBERT_BASE_URL", "https://albert.api.etalab.gouv.fr/v1")
LLM_MODEL = _config("LLM_MODEL", "openai/gpt-oss-120b")

if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"
THEME = st.session_state["theme"]

PALETTES = {
    "dark": {
        "bg": "#1d2327",
        "bg-elev": "#2a2f33",
        "card-bg": "#202023",
        "code-bg": "#15191c",
        "border": "#3a3f44",
        "text": "#fefefe",
        "text-secondary": "#c2c3c8",
        "text-muted": "#7a7b80",
        "accent": "#E67E22",
        "accent-strong": "#f39c3e",
        "shadow": "rgba(0,0,0,0.4)",
    },
    "light": {
        "bg": "#faf8f4",
        "bg-elev": "#f1ede6",
        "card-bg": "#ffffff",
        "code-bg": "#f4f1ea",
        "border": "#e2ddd3",
        "text": "#22201c",
        "text-secondary": "#4d4a44",
        "text-muted": "#8a857c",
        "accent": "#E67E22",
        "accent-strong": "#c9670f",
        "shadow": "rgba(30,20,10,0.08)",
    },
}
PALETTE = PALETTES[THEME]

CATEGORIES_FR = [
    (
        "connotation", "Connotation",
        "Charges affectives et jugements de valeur portés par le choix des mots, "
        "au-delà de leur sens littéral.",
        "#F59E0B",
    ),
    (
        "subtext", "Sous-texte",
        "Message implicite véhiculé par le ton, la posture ou la mise en scène du propos.",
        "#A855F7",
    ),
    (
        "implicature", "Implicature",
        "Ce que le texte laisse entendre sans l'affirmer, par sous-entendu logique "
        "ou conversationnel.",
        "#3B82F6",
    ),
    (
        "defacto", "De facto",
        "Affirmations présentées comme des faits établis, sans source ni nuance, "
        "qui mériteraient d'être qualifiées.",
        "#EF4444",
    ),
    (
        "implementation", "Détail d'implémentation",
        "Conditions matérielles, techniques ou organisationnelles nécessaires "
        "mais passées sous silence.",
        "#10B981",
    ),
    (
        "omission", "Omission pure",
        "Dimensions absentes du texte alors qu'elles sont structurantes "
        "pour le sujet traité.",
        "#EC4899",
    ),
]

CATEGORIES_EN = [
    (
        "connotation", "Connotation",
        "Emotional charge and value judgments carried by word choice, "
        "beyond their literal meaning.",
        "#F59E0B",
    ),
    (
        "subtext", "Subtext",
        "Implicit message conveyed by tone, posture, or the way the point is framed.",
        "#A855F7",
    ),
    (
        "implicature", "Implicature",
        "What the text lets you infer without stating it, through logical "
        "or conversational implication.",
        "#3B82F6",
    ),
    (
        "defacto", "De facto",
        "Claims presented as established facts, without source or nuance, "
        "that deserve qualification.",
        "#EF4444",
    ),
    (
        "implementation", "Implementation detail",
        "Material, technical, or organizational conditions that are "
        "necessary but left unsaid.",
        "#10B981",
    ),
    (
        "omission", "Pure omission",
        "Dimensions absent from the text even though they are central "
        "to the topic.",
        "#EC4899",
    ),
]

CATEGORIES = CATEGORIES_FR if LANG == "fr" else CATEGORIES_EN


def _load_system_instruction(lang: str) -> str:
    filename = "INSTRUCTION.md" if lang == "fr" else "INSTRUCTION_EN.md"
    content = (Path(__file__).parent / filename).read_text(encoding="utf-8")
    return content.split("\n---\n", 1)[1].strip()


AUDIT_SYSTEM_INSTRUCTION = _load_system_instruction(LANG)

STRINGS = {
    "fr": {
        "title_l1": "Voyage au pays ",
        "title_l2": "du non-écrit",
        "subtitle": "Audit des implicites, sous-textes et angles morts des réponses proposées par un LLM.",
        "intro": "Collez une réponse produite par un modèle de langage (ChatGPT, Claude, Gemini, Mistral…) pour en révéler les non-dits.",
        "ai_notice": "Analyse générée par un modèle d'IA, pas une vérité absolue (détails en pied de page).",
        "question_label": "Contexte / question posée — *optionnel*",
        "question_placeholder": "La question initiale ou le contexte dans lequel la réponse a été produite...",
        "answer_label": "**Réponse à auditer**",
        "answer_placeholder": "Collez ici la réponse du modèle à analyser...",
        "submit_button": "Révéler le non-écrit →",
        "warning_empty": "Veuillez coller la réponse à auditer.",
        "warning_rate_limit": "Veuillez patienter {n} secondes entre deux analyses.",
        "spinner": "Analyse des implicites en cours…",
        "error_json": "Le modèle n'a pas renvoyé un JSON valide. Réessayez.",
        "error_api": "Erreur de communication avec l'API Albert. Réessayez dans quelques instants.",
        "error_generic": "Une erreur inattendue s'est produite. Réessayez.",
        "error_analysis": "Erreur d'analyse : {e}",
        "synthesis_label": "Synthèse de l'audit",
        "section_title": "Le non-écrit révélé",
        "section_count": "6 catégories · {n} non-dits",
        "instr_label": "Instruction à renvoyer au modèle d'origine",
        "copy_button": "Copier",
        "copy_confirm": "Copié ✓",
        "export_button": "↓ Exporter l'audit (Markdown)",
        "export_filename": "audit-implicites.md",
        "new_audit_button": "↺ Nouvel audit",
        "dialog_title": "Nouvel audit",
        "dialog_warning": "⚠️ Attention, l'audit actuel sera effacé. Continuer ?",
        "dialog_cancel": "Annuler",
        "dialog_confirm": "Effacer et continuer",
        "toggle_theme_help": "Basculer entre thème clair et sombre",
        "toggle_lang_help": "Switch to English",
        "footer_inspired": 'Inspiré par <a href="https://www.linkedin.com/pulse/voyage-au-pays-du-non-%C3%A9crit-arthur-sarazin-phd-hwswe" target="_blank">Voyage au pays du non-écrit</a> d\'<span class="name">Arthur Sarazin</span>',
        "footer_model": 'Modèle <span class="name">{model}</span> via l\'<a href="https://albert.api.etalab.gouv.fr" target="_blank">API Albert</a> · hébergé sur <a href="https://render.com" target="_blank">Render</a> (<span class="name">Francfort, UE</span>)',
        "footer_dev": 'Développé avec Claude Code · <a href="https://github.com/uneIAparjour/non-ecrit" target="_blank">dépôt GitHub</a>',
        "footer_license": 'CC BY 4.0 — <span class="name">Bertrand Formet</span> pour <a href="https://uneIAparjour.fr" target="_blank">uneIAparjour.fr</a>',
        "expander_title": "Confidentialité",
        "privacy_md": """
**Traitement des données**
Le texte que vous collez (réponse à auditer, question de contexte) est transmis à l'API Albert
(DINUM / Etalab, infrastructure d'IA souveraine française) le temps de l'analyse, puis n'est
conservé ni par cette application ni dans une base de données : aucun stockage persistant côté
serveur, seule la mémoire de session de votre navigateur garde le dernier résultat, et elle est
effacée à la fermeture de l'onglet. L'application ne dépose aucun cookie de suivi et ne collecte
aucune donnée personnelle.

**Contenu généré par IA**
La synthèse, les catégories de non-dits et l'instruction de correction affichées sont produites
par le modèle de langage indiqué ci-dessus via l'API Albert, conformément à l'obligation de
transparence du règlement européen sur l'IA (AI Act, art. 50) : ce contenu est signalé comme
généré artificiellement et reste une analyse automatisée, pas une vérité absolue.

**Contact**
Une question sur le traitement de vos données ? [contact@uneiaparjour.fr](mailto:contact@uneiaparjour.fr)
""".strip(),
        "export_title": "# Audit de l'implicite — Résultats\n",
        "export_question": "## Question analysée\n{q}\n",
        "export_answer": "## Réponse auditée\n{a}\n",
        "export_synthesis": "## Synthèse\n{s}\n",
        "export_nothing": "_Rien de notable._",
        "export_correction_title": "## Instruction de correction\n",
        "export_correction_intro": "Copiez-collez cette consigne dans votre conversation avec le modèle d'origine :\n",
        "export_credit": (
            "---\n_Généré par [Voyage au pays du non-écrit](https://github.com/uneIAparjour/non-ecrit) "
            "— CC BY 4.0 Bertrand Formet pour [uneIAparjour](https://uneIAparjour.fr)_"
        ),
        "api_key_missing": "Clé API Albert non configurée dans les secrets Streamlit.",
    },
    "en": {
        "title_l1": "The Unwritten ",
        "title_l2": "Journey",
        "subtitle": "Auditing the implicit, the subtext, and the blind spots in LLM responses.",
        "intro": "Paste a response produced by a language model (ChatGPT, Claude, Gemini, Mistral…) to reveal what it leaves unsaid.",
        "ai_notice": "Analysis generated by an AI model, not an absolute truth (details in the footer).",
        "question_label": "Context / question asked — *optional*",
        "question_placeholder": "The original question or context in which the response was produced...",
        "answer_label": "**Response to audit**",
        "answer_placeholder": "Paste the model's response to analyze here...",
        "submit_button": "Reveal the unwritten →",
        "warning_empty": "Please paste the response to audit.",
        "warning_rate_limit": "Please wait {n} seconds between two analyses.",
        "spinner": "Analyzing implicit content…",
        "error_json": "The model did not return valid JSON. Please try again.",
        "error_api": "Error communicating with the Albert API. Please try again shortly.",
        "error_generic": "An unexpected error occurred. Please try again.",
        "error_analysis": "Analysis error: {e}",
        "synthesis_label": "Audit synthesis",
        "section_title": "The unwritten, revealed",
        "section_count": "6 categories · {n} unstated elements",
        "instr_label": "Instruction to send back to the original model",
        "copy_button": "Copy",
        "copy_confirm": "Copied ✓",
        "export_button": "↓ Export audit (Markdown)",
        "export_filename": "implicit-audit.md",
        "new_audit_button": "↺ New audit",
        "dialog_title": "New audit",
        "dialog_warning": "⚠️ Warning, the current audit will be erased. Continue?",
        "dialog_cancel": "Cancel",
        "dialog_confirm": "Clear and continue",
        "toggle_theme_help": "Toggle light / dark theme",
        "toggle_lang_help": "Passer en français",
        "footer_inspired": 'Inspired by <a href="https://www.linkedin.com/pulse/voyage-au-pays-du-non-%C3%A9crit-arthur-sarazin-phd-hwswe" target="_blank">Voyage au pays du non-écrit</a> by <span class="name">Arthur Sarazin</span>',
        "footer_model": 'Model <span class="name">{model}</span> via the <a href="https://albert.api.etalab.gouv.fr" target="_blank">Albert API</a> · hosted on <a href="https://render.com" target="_blank">Render</a> (<span class="name">Frankfurt, EU</span>)',
        "footer_dev": 'Built with Claude Code · <a href="https://github.com/uneIAparjour/non-ecrit" target="_blank">GitHub repo</a>',
        "footer_license": 'CC BY 4.0 — <span class="name">Bertrand Formet</span> for <a href="https://uneIAparjour.fr" target="_blank">uneIAparjour.fr</a>',
        "expander_title": "Privacy",
        "privacy_md": """
**Data processing**
The text you paste (response to audit, context question) is sent to the Albert API
(DINUM / Etalab, French sovereign AI infrastructure) for the duration of the analysis, then is
kept neither by this application nor in any database: no persistent server-side storage, only
your browser's session memory holds the last result, and it is cleared when the tab is closed.
The application does not set any tracking cookies and does not collect any personal data.

**AI-generated content**
The synthesis, the categories of unstated content, and the correction instruction shown are
produced by the language model indicated above via the Albert API, in line with the transparency
obligation of the EU AI Act (art. 50): this content is flagged as artificially generated and
remains an automated analysis, not an absolute truth.

**Contact**
A question about how your data is handled? [contact@uneiaparjour.fr](mailto:contact@uneiaparjour.fr)
""".strip(),
        "export_title": "# Implicit Audit — Results\n",
        "export_question": "## Question analyzed\n{q}\n",
        "export_answer": "## Response audited\n{a}\n",
        "export_synthesis": "## Synthesis\n{s}\n",
        "export_nothing": "_Nothing notable._",
        "export_correction_title": "## Correction instruction\n",
        "export_correction_intro": "Copy and paste this instruction into your conversation with the original model:\n",
        "export_credit": (
            "---\n_Generated by [Voyage au pays du non-écrit](https://github.com/uneIAparjour/non-ecrit) "
            "— CC BY 4.0 Bertrand Formet for [uneIAparjour](https://uneIAparjour.fr)_"
        ),
        "api_key_missing": "Albert API key not configured in Streamlit secrets.",
    },
}
S = STRINGS[LANG]

# ---------------------------------------------------------------------------
# Style — hifi from Claude Design handoff
# ---------------------------------------------------------------------------

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Spline+Sans:wght@400;500;600;700&display=swap');

:root {{
  --vnt-bg: {PALETTE["bg"]};
  --vnt-bg-elev: {PALETTE["bg-elev"]};
  --vnt-card-bg: {PALETTE["card-bg"]};
  --vnt-code-bg: {PALETTE["code-bg"]};
  --vnt-border: {PALETTE["border"]};
  --vnt-text: {PALETTE["text"]};
  --vnt-text-secondary: {PALETTE["text-secondary"]};
  --vnt-text-muted: {PALETTE["text-muted"]};
  --vnt-accent: {PALETTE["accent"]};
  --vnt-accent-strong: {PALETTE["accent-strong"]};
  --vnt-shadow: {PALETTE["shadow"]};
}}

/* Header */
.vnt-title {{
  font-family: 'Instrument Serif', Georgia, serif;
  font-weight: 400; font-size: 72px; line-height: 1.05;
  letter-spacing: -0.5px; margin: 0 0 28px;
}}
.vnt-title .l1 {{ color: var(--vnt-text); }}
.vnt-title .l2 {{ font-style: italic; color: var(--vnt-accent); }}
.vnt-subtitle {{
  margin: 0 0 48px; max-width: 640px;
  font-family: 'Spline Sans', sans-serif;
  font-size: 19px; line-height: 1.55; color: var(--vnt-text-secondary);
  font-style: italic;
}}
.vnt-ai-notice {{
  margin: 0 0 32px;
  font-family: 'Spline Sans', sans-serif;
  font-size: 13px; color: var(--vnt-text-muted);
}}

/* Reclaim the space reserved for Streamlit's own (hidden) header bar */
[data-testid="stHeader"] {{ display: none !important; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 24px !important; }}

/* Theme + language toggles — anchored to the content column, level with the title */
[data-testid="stMainBlockContainer"] {{ position: relative; }}
.st-key-theme_toggle {{ position: absolute; top: 34px; right: 0; z-index: 10; }}
.st-key-lang_toggle {{ position: absolute; top: 34px; right: 40px; z-index: 10; }}
.st-key-theme_toggle button, .st-key-lang_toggle button {{
  width: auto; height: auto; padding: 4px; min-height: 0;
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: var(--vnt-text-muted) !important; display: flex; align-items: center; justify-content: center;
  opacity: 0.75; transition: color .15s ease, opacity .15s ease;
}}
.st-key-theme_toggle button:hover, .st-key-lang_toggle button:hover {{ color: var(--vnt-accent) !important; opacity: 1; }}

/* Synthesis callout */
.vnt-synth {{
  border-left: 3px solid var(--vnt-accent);
  background: rgba(230,126,34,0.15);
  border-radius: 0 8px 8px 0;
  padding: 18px 22px; margin-bottom: 28px;
}}
.vnt-synth-label {{
  font-family: 'Spline Sans', sans-serif;
  font-size: 12px; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: var(--vnt-accent-strong); margin-bottom: 8px;
}}
.vnt-synth-text {{
  font-family: 'Spline Sans', sans-serif;
  font-size: 16.5px; line-height: 1.65; color: var(--vnt-text); margin: 0;
}}

/* Section heading */
.vnt-section-head {{
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 18px;
}}
.vnt-section-title {{
  font-family: 'Instrument Serif', Georgia, serif;
  font-style: italic; font-weight: 400; font-size: 30px;
  color: var(--vnt-text); margin: 0;
}}
.vnt-section-count {{
  font-family: 'Spline Sans', sans-serif;
  font-size: 13px; color: var(--vnt-text-muted);
}}

/* Category cards */
.vnt-card {{
  background: var(--vnt-card-bg); border: 1px solid var(--vnt-border);
  border-left-width: 3px; border-left-style: solid;
  border-radius: 0 10px 10px 0; padding: 18px 22px; margin-bottom: 14px;
}}
.vnt-card-head {{
  display: flex; align-items: center; gap: 10px; margin-bottom: 11px;
}}
.vnt-card-dot {{
  width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0;
}}
.vnt-card-title {{
  font-family: 'Spline Sans', sans-serif;
  font-size: 17px; font-weight: 700; color: var(--vnt-text);
}}
.vnt-card-pill {{
  margin-left: auto; padding: 3px 10px; border-radius: 20px;
  font-family: 'Spline Sans', sans-serif;
  font-size: 12px; font-weight: 600;
}}
.vnt-card-items {{
  margin: 0; padding-left: 0; list-style: none;
  display: flex; flex-direction: column; gap: 9px;
}}
.vnt-card-items li {{
  font-family: 'Spline Sans', sans-serif;
  font-size: 16px; line-height: 1.6; color: var(--vnt-text-secondary);
  padding-left: 16px; position: relative;
}}

/* Tooltip */
.vnt-tip {{ position: relative; display: inline-flex; align-items: center; cursor: help; }}
.vnt-tip-dot {{
  width: 16px; height: 16px; border-radius: 50%;
  border: 1px solid var(--vnt-text-muted); color: var(--vnt-text-muted);
  font-size: 11px; font-weight: 700;
  display: inline-flex; align-items: center; justify-content: center;
}}
.vnt-tipbox {{
  visibility: hidden; opacity: 0; transition: opacity .15s ease;
  position: absolute; bottom: 140%; left: 50%; transform: translateX(-50%);
  width: 240px; background: var(--vnt-bg-elev); border: 1px solid var(--vnt-border);
  border-radius: 8px; padding: 10px 12px;
  font-family: 'Spline Sans', sans-serif;
  font-size: 12.5px; line-height: 1.5; color: var(--vnt-text-secondary);
  z-index: 5; box-shadow: 0 8px 24px var(--vnt-shadow);
}}
.vnt-tip:hover .vnt-tipbox {{ visibility: visible; opacity: 1; }}

/* Instruction block */
.vnt-instr {{
  margin-top: 32px;
  border-left: 3px solid #10B981;
  background: rgba(16,185,129,0.08);
  border-radius: 0 10px 10px 0; padding: 20px 22px;
}}
.vnt-instr-label {{
  font-family: 'Spline Sans', sans-serif;
  font-size: 12px; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: #10B981; margin-bottom: 12px;
}}
.vnt-instr-wrap {{ display: flex; flex-direction: column; gap: 10px; }}
.vnt-instr-pre {{
  margin: 0; background: var(--vnt-code-bg); border: 1px solid var(--vnt-border);
  border-radius: 8px; padding: 18px;
  font-family: 'Spline Sans', sans-serif;
  font-size: 15px; line-height: 1.65; color: var(--vnt-text-secondary);
  white-space: pre-wrap; overflow-x: auto;
}}
.vnt-copy-btn {{
  align-self: flex-end;
  background: var(--vnt-bg-elev); color: var(--vnt-text-secondary);
  border: 1px solid var(--vnt-border); border-radius: 6px;
  padding: 8px 16px; font-size: 13px; font-weight: 600;
  cursor: pointer; font-family: 'Spline Sans', sans-serif;
  transition: border-color .15s ease, color .15s ease;
}}
.vnt-copy-btn:hover {{ border-color: #10B981; color: #10B981; }}

/* Footer */
.vnt-footer {{
  margin-top: 72px; padding: 28px 0 24px;
  border-top: 1px solid var(--vnt-border);
  font-family: 'Spline Sans', sans-serif;
  font-size: 13px; line-height: 1.7; color: var(--vnt-text-muted); text-align: center;
}}
.vnt-footer a {{ color: var(--vnt-accent); text-decoration: none; }}
.vnt-footer a:hover {{ text-decoration: underline; }}
.vnt-footer .name {{ color: var(--vnt-text-secondary); }}

/* Native Streamlit component overrides — keep them in sync with the toggle */
.stApp {{ background-color: var(--vnt-bg) !important; }}
[data-testid="stHeader"] {{ background-color: var(--vnt-bg) !important; }}
[data-testid="stAppViewContainer"] {{ color: var(--vnt-text); }}
[data-testid="stWidgetLabel"] p {{ color: var(--vnt-text) !important; font-family: 'Spline Sans', sans-serif; }}
.stTextArea textarea {{
  background-color: var(--vnt-card-bg) !important; color: var(--vnt-text) !important;
  border-color: var(--vnt-border) !important;
}}
.stTextArea textarea::placeholder {{ color: var(--vnt-text-muted) !important; opacity: 1; }}
[data-testid="stAlert"] {{
  background-color: var(--vnt-bg-elev) !important; border: 1px solid var(--vnt-border) !important;
}}
[data-testid="stAlert"] p {{ color: var(--vnt-text) !important; }}
.stDownloadButton button {{
  background-color: var(--vnt-bg-elev) !important; color: var(--vnt-text) !important;
  border: 1px solid var(--vnt-border) !important;
}}
.stDownloadButton button:hover {{ border-color: var(--vnt-accent) !important; color: var(--vnt-accent) !important; }}
[data-testid="stExpander"] {{
  border: 1px solid var(--vnt-border) !important; border-radius: 10px !important;
  background: var(--vnt-card-bg) !important; margin-top: 8px;
}}
[data-testid="stExpander"] summary {{
  font-family: 'Spline Sans', sans-serif; background-color: var(--vnt-card-bg) !important;
  border-radius: 10px;
}}
[data-testid="stExpander"] summary p {{ color: var(--vnt-text-secondary) !important; font-size: 13px; }}
[data-testid="stExpander"] summary svg {{ fill: var(--vnt-text-secondary) !important; }}
[data-testid="stExpanderDetails"] p, [data-testid="stExpanderDetails"] li {{
  color: var(--vnt-text-secondary) !important; font-family: 'Spline Sans', sans-serif; font-size: 14px; line-height: 1.6;
}}
[data-testid="stExpanderDetails"] strong {{ color: var(--vnt-text) !important; }}
[data-testid="stExpanderDetails"] a {{ color: var(--vnt-accent) !important; }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Theme + language toggles
# ---------------------------------------------------------------------------

_toggle_icon = ":material/dark_mode:" if THEME == "dark" else ":material/light_mode:"
if st.button("", key="theme_toggle", help=S["toggle_theme_help"], icon=_toggle_icon):
    st.session_state["theme"] = "light" if THEME == "dark" else "dark"
    st.rerun()

if st.button("", key="lang_toggle", help=S["toggle_lang_help"], icon=":material/language:"):
    st.session_state["lang"] = "en" if LANG == "fr" else "fr"
    st.rerun()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    f'<h1 class="vnt-title"><span class="l1">{S["title_l1"]}</span>'
    f'<span class="l2">{S["title_l2"]}</span></h1>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="vnt-subtitle">{S["subtitle"]}</p>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<p style="margin-bottom: 8px;">{S["intro"]}</p>'
    f'<p class="vnt-ai-notice">{S["ai_notice"]}</p>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_albert(messages: list[dict]) -> str:
    if not ALBERT_API_KEY:
        st.error(S["api_key_missing"])
        st.stop()
    resp = httpx.post(
        f"{ALBERT_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {ALBERT_API_KEY}", "Content-Type": "application/json"},
        json={"model": LLM_MODEL, "messages": messages, "temperature": 0.3},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


EXPECTED_KEYS = {"connotation", "subtext", "implicature", "defacto", "implementation", "omission"}


def run_audit(question: str, answer: str) -> dict:
    a_label = "RÉPONSE DU LLM" if LANG == "fr" else "LLM RESPONSE"
    user_content = (
        f"QUESTION : {question}\n\n{a_label} :\n{answer}"
        if question
        else f"{a_label} :\n{answer}"
    )
    messages = [
        {"role": "system", "content": AUDIT_SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_content},
    ]
    raw = call_albert(messages)
    json_str = raw
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        json_str = match.group(1)
    try:
        data = json.loads(json_str.strip())
    except json.JSONDecodeError:
        raise ValueError(S["error_json"])
    for key in EXPECTED_KEYS:
        if key not in data:
            data[key] = []
    if "synthesis" not in data:
        data["synthesis"] = ""
    if "correction_prompt" not in data:
        data["correction_prompt"] = ""
    return data


def format_export(audit: dict, question: str, answer: str) -> str:
    lines = [S["export_title"]]
    if question:
        lines.append(S["export_question"].format(q=question))
    lines.append(S["export_answer"].format(a=answer))
    lines.append("---\n")
    if audit.get("synthesis"):
        lines.append(S["export_synthesis"].format(s=audit["synthesis"]))
    for cat_id, label, tip, _ in CATEGORIES:
        items = audit.get(cat_id, [])
        lines.append(f"### {label}")
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append(S["export_nothing"])
        lines.append("")
    if audit.get("correction_prompt"):
        lines.append("---\n")
        lines.append(S["export_correction_title"])
        lines.append(S["export_correction_intro"])
        lines.append(f"> {audit['correction_prompt']}\n")
    lines.append(S["export_credit"])
    return "\n".join(lines)


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _esc(text: str) -> str:
    return html.escape(str(text))


@st.dialog(S["dialog_title"])
def _confirm_new_audit():
    st.write(S["dialog_warning"])
    col1, col2 = st.columns(2)
    with col1:
        if st.button(S["dialog_cancel"], use_container_width=True):
            st.rerun()
    with col2:
        if st.button(S["dialog_confirm"], type="primary", use_container_width=True):
            for key in ("audit_result", "audit_question", "audit_answer"):
                st.session_state.pop(key, None)
            st.session_state["question_input"] = ""
            st.session_state["answer_input"] = ""
            st.rerun()


def render_results(audit: dict, question: str = "", answer: str = ""):
    # Synthesis
    if audit.get("synthesis"):
        st.markdown(
            '<div class="vnt-synth">'
            f'<div class="vnt-synth-label">{S["synthesis_label"]}</div>'
            f'<p class="vnt-synth-text">{_esc(audit["synthesis"])}</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    # Section heading
    total = sum(len(audit.get(c[0], [])) for c in CATEGORIES)
    st.markdown(
        '<div class="vnt-section-head">'
        f'<h2 class="vnt-section-title">{S["section_title"]}</h2>'
        f'<span class="vnt-section-count">{S["section_count"].format(n=total)}</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Cards
    for cat_id, label, tip, color in CATEGORIES:
        items = audit.get(cat_id, [])
        count = len(items)
        bg = _hex_to_rgba(color, 0.15)

        items_html = ""
        if items:
            lis = "".join(
                f'<li><span style="position:absolute;left:0;top:0;color:{color};">•</span>{_esc(item)}</li>'
                for item in items
            )
            items_html = f'<ul class="vnt-card-items">{lis}</ul>'

        st.markdown(
            f'<div class="vnt-card" style="border-left-color:{color}">'
            f'<div class="vnt-card-head">'
            f'<span class="vnt-card-dot" style="background:{color}"></span>'
            f'<span class="vnt-card-title">{label}</span>'
            f'<span class="vnt-tip"><span class="vnt-tip-dot">?</span>'
            f'<span class="vnt-tipbox">{tip}</span></span>'
            f'<span class="vnt-card-pill" style="color:{color};background:{bg}">{count}</span>'
            f'</div>'
            f'{items_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Instruction block
    if audit.get("correction_prompt"):
        safe_prompt = _esc(audit["correction_prompt"])
        st.markdown(
            '<div class="vnt-instr">'
            f'<div class="vnt-instr-label">{S["instr_label"]}</div>'
            '<div class="vnt-instr-wrap">'
            f'<pre class="vnt-instr-pre" id="vnt-instruction">{safe_prompt}</pre>'
            '<button class="vnt-copy-btn" onclick="'
            "var t=document.getElementById('vnt-instruction').textContent;"
            "navigator.clipboard.writeText(t).then(function(){"
            f"var b=event.target;b.textContent='{S['copy_confirm']}';"
            f"setTimeout(function(){{b.textContent='{S['copy_button']}'}},1800)}});"
            f'">{S["copy_button"]}</button>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # Export
    export_md = format_export(audit, question, answer)
    st.download_button(
        label=S["export_button"],
        data=export_md,
        file_name=S["export_filename"],
        mime="text/markdown",
        use_container_width=True,
    )

    if st.button(S["new_audit_button"], use_container_width=True, key="new_audit_btn"):
        _confirm_new_audit()

# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------

RATE_LIMIT_SECONDS = 15

question = st.text_area(
    S["question_label"],
    placeholder=S["question_placeholder"],
    height=80,
    key="question_input",
)
answer = st.text_area(
    S["answer_label"],
    placeholder=S["answer_placeholder"],
    height=220,
    key="answer_input",
)
if st.button(S["submit_button"], type="primary", use_container_width=True):
    if not answer.strip():
        st.warning(S["warning_empty"])
    else:
        last_call = st.session_state.get("last_call_time", 0)
        if time.time() - last_call < RATE_LIMIT_SECONDS:
            st.warning(S["warning_rate_limit"].format(n=RATE_LIMIT_SECONDS))
        else:
            with st.spinner(S["spinner"]):
                try:
                    q = question.strip()
                    a = answer.strip()
                    audit = run_audit(q, a)
                    st.session_state["last_call_time"] = time.time()
                    st.session_state["audit_result"] = audit
                    st.session_state["audit_question"] = q
                    st.session_state["audit_answer"] = a
                except (ValueError, json.JSONDecodeError) as e:
                    st.error(S["error_analysis"].format(e=e))
                except httpx.HTTPStatusError:
                    st.error(S["error_api"])
                except Exception:
                    st.error(S["error_generic"])

if st.session_state.get("audit_result"):
    render_results(
        st.session_state["audit_result"],
        st.session_state.get("audit_question", ""),
        st.session_state.get("audit_answer", ""),
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="vnt-footer">'
    f'<div>{S["footer_inspired"]}</div>'
    f'<div>{S["footer_model"].format(model=LLM_MODEL)}</div>'
    f'<div>{S["footer_dev"]}</div>'
    f'<div style="margin-top:8px;">{S["footer_license"]}</div>'
    '</div>',
    unsafe_allow_html=True,
)

with st.expander(S["expander_title"]):
    st.markdown(S["privacy_md"])

# ---------------------------------------------------------------------------
# Auto-resize when embedded in an iframe (posts our real height to the
# parent page — see README for the matching listener script to add there).
# ---------------------------------------------------------------------------

components.html(
    """
    <script>
    (function () {
      function contentEl() {
        var doc = window.parent.document;
        return doc.querySelector('[data-testid="stMainBlockContainer"]')
          || doc.querySelector('[data-testid="stMain"]')
          || doc.documentElement;
      }
      function reportHeight() {
        try {
          var h = contentEl().scrollHeight + 32;
          window.top.postMessage({ type: "iframeResize", height: h }, "*");
        } catch (e) {}
      }
      reportHeight();
      window.addEventListener("load", reportHeight);
      try {
        new ResizeObserver(reportHeight).observe(contentEl());
      } catch (e) {}
      setInterval(reportHeight, 500);
    })();
    </script>
    """,
    height=0,
)
