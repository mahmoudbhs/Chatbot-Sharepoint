# Chatbot SharePoint / M365

Assistant conversationnel local pour SharePoint, Teams, OneDrive et Outlook.

Le projet combine :
- un moteur conversationnel Python
- une base documentaire locale
- une API Flask
- une interface web simple
- un mode LLM optionnel en surcouche

## Fonctionnalites

- Reponses sur SharePoint, Teams, OneDrive et Outlook
- Changement de sujet au fil de la conversation
- Clarification des demandes incompletes
- Redirections intelligentes a partir d'une base documentaire locale
- Memoire persistante legere par session
- Mode "reponse fiable uniquement" pour eviter les indications hasardeuses
- Mode LLM optionnel pour reformuler les reponses sans remplacer le moteur actuel

## Structure

```text
ML-Chatbot/
├── API/
│   ├── app.py
│   ├── chatbot.py
│   ├── engine.py
│   ├── knowledge_base.py
│   ├── llm_client.py
│   ├── memory_store.py
│   └── sharepoint_connector.py
├── DATA/
│   ├── intents.json
│   ├── responses.json
│   ├── training_data.json
│   ├── knowledge_documents.json
│   └── user_memory.json
├── FRONTEND/
│   ├── chat.html
│   ├── chat.js
│   └── chat.css
├── MODELS/
│   └── train_model.py
├── TESTS/
│   └── test_chatbot.py
├── .env.example
├── .gitignore
└── requirements.txt
```

## Installation

Depuis le dossier du projet :

```powershell
cd C:\Users\amatek\chatbot\ML-Chatbot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Lancer le projet

### 1. Entrainer / generer l'artefact

```powershell
python MODELS\train_model.py
```

### 2. Lancer l'API Flask

```powershell
python API\app.py
```

### 3. Ouvrir l'interface

```text
http://localhost:5000
```

## Lancer les tests

```powershell
python -m unittest discover -s TESTS -p "test_*.py" -v
```



## Sources de reponse

Le moteur repond en priorite a partir de :

1. la base documentaire locale [knowledge_documents.json](../DATA/knowledge_documents.json)
2. la logique metier dans [engine.py](../API/engine.py)
3. les intents et exemples dans [intents.json](../DATA/intents.json) et [training_data.json](../DATA/training_data.json)
4. un connecteur SharePoint live si configure
5. un LLM optionnel pour reformuler, jamais comme source de verite

## Mode fiable

Le chatbot essaie d'eviter les reponses hasardeuses :

- si une source fiable existe, il repond
- si la demande est incomplete, il demande une clarification
- si la base ne couvre pas assez bien la question, il prefere le dire plutot que d'inventer

## Ce que le projet sait deja faire

- questions simples sur SharePoint, Teams, OneDrive et Outlook
- orientation sur un sujet (`sharepoint`, `onedrive`, etc.)
- suivi de conversation
- gestion du small talk (`salut`, `ca va`, `merci`)
- clarifications sur les demandes trop courtes (`je veux`, `je souhaite`)

## Limites actuelles

- pas de synchronisation SharePoint temps reel sans configuration live
- base documentaire locale a enrichir si tu veux couvrir plus de cas
- le LLM reste optionnel et ne remplace pas le moteur
- les permissions utilisateurs reelles ne sont pas encore gerees

## Bonnes pratiques

- enrichir [knowledge_documents.json](../DATA/knowledge_documents.json) avec des contenus valides
- garder le `.env` en local seulement
- relancer `train_model.py` apres modification des intents ou exemples
- lancer les tests avant chaque push

## Fichiers sensibles

Ces fichiers ne doivent pas etre pushes :

- `.env`
- `.venv/`
- `DATA/user_memory.json`
- `MODELS/chatbot_artifacts.pkl`
- `__pycache__/`

Le projet utilise [`.gitignore`](../.gitignore) pour les exclure.
