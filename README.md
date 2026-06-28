# Voyage au pays du non-écrit

Audit des implicites, sous-textes et angles morts dans une réponse de modèle de langage.

## Le problème

La réponse d'un LLM, aussi vraisemblable soit-elle, comporte des manques : des implicites que le modèle tient pour acquis, des conclusions logiques qu'il ne tire pas, des angles qu'il n'aborde pas. Ces non-dits sont invisibles pour l'utilisateur et c'est précisément ce que la délégation à la machine rend jsutement visible.

## L'approche

L'outil s'appuie sur une taxonomie de l'implicite issue de l'ontologie Wikidata, formalisée par [Arthur Sarazin](https://www.linkedin.com/pulse/voyage-au-pays-du-non-%C3%A9crit-arthur-sarazin-phd-hwswe). Chaque réponse est auditée selon 6 catégories :

| Catégorie | Ce qu'elle révèle |
|---|---|
| **Connotation** | Ce que les mots choisis véhiculent sans le dire |
| **Sous-texte** | L'intention ou le positionnement sous-jacent non formulé |
| **Implicature** | Ce qui découle logiquement mais n'est pas tiré comme conclusion |
| **De facto** | Ce qui est vrai en pratique mais non reconnu |
| **Détail d'implémentation** | Ce qu'il faudrait savoir pour agir concrètement |
| **Omission pure** | Les angles, perspectives ou faits simplement non abordés |

## Utilisation

Deux modes :

- **Coller un texte** — collez une réponse LLM (et optionnellement la question qui l'a produite) pour lancer l'audit
- **Chat intégré** — posez une question, obtenez une réponse, puis auditez-la en un clic

## Déploiement

L'application tourne sur [Streamlit Cloud](https://streamlit.io/cloud) et utilise l'[API Albert](https://albert.api.etalab.gouv.fr) comme moteur d'analyse.

### En local

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Renseigner ALBERT_API_KEY dans secrets.toml
streamlit run app.py
```

### Sur Streamlit Cloud

1. Connecter le repo GitHub
2. Pointer sur `app.py`
3. Dans **Settings → Secrets**, ajouter :

```toml
ALBERT_API_KEY = "votre-clé"
```

## Crédits

- Taxonomie de l'implicite : [Arthur Sarazin](https://www.linkedin.com/pulse/voyage-au-pays-du-non-%C3%A9crit-arthur-sarazin-phd-hwswe)
- Moteur LLM : [API Albert](https://albert.api.etalab.gouv.fr) (DINUM / Etalab)
