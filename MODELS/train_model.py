import json
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

# Charger les données
with open('../DATA/intents.json', 'r', encoding='utf-8') as f:    data = json.load(f)

# Préparer les données d'entraînement
X = []  # Questions
y = []  # Labels (tags)

for intent in data['intents']:
    for pattern in intent['patterns']:
        X.append(pattern.lower())
        y.append(intent['tag'])

print(f"Dataset : {len(X)} exemples, {len(set(y))} classes")

# Split train/test
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Créer le pipeline ML
model = Pipeline([
    ('vectorizer', TfidfVectorizer(
        ngram_range=(1, 3),      # Unigrammes, bigrammes, trigrammes
        max_features=1000,       # Top 1000 features
        lowercase=True,
        analyzer='word'
    )),
    ('classifier', LinearSVC(
        C=1.0,
        max_iter=1000,
        class_weight='balanced'  # Gérer déséquilibre classes
    ))
])

# Entraînement
print("Entraînement du modèle...")
model.fit(X_train, y_train)

# Évaluation
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"\nAccuracy : {accuracy*100:.2f}%")
print("\nRapport détaillé :")
print(classification_report(y_test, y_pred))

# Sauvegarder le modèle
with open('intent_classifier.pkl', 'wb') as f:
    pickle.dump(model, f)

print("\n Modèle sauvegardé : intent_classifier.pkl")

# Test manuel
print("\n--- Tests manuels ---")
test_questions = [
    "Comment je partage un fichier Teams ?",
    "Créer une réunion",
    "C'est quoi la différence entre OneDrive et SharePoint",
    "Bonjour",
    "Au revoir"
]

for question in test_questions:
    predicted = model.predict([question.lower()])[0]
    print(f"Q: {question}")
    print(f"→ Intent détecté : {predicted}\n")