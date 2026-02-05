import random
import json
import pickle
import numpy as np
import nltk
from nltk.stem import WordNetLemmatizer
from tensorflow.keras.models import load_model
import os

# Initialiser le lemmatizer
lemmatizer = WordNetLemmatizer()

# Chemins des fichiers
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'DATA')
MODELS_DIR = os.path.join(BASE_DIR, 'MODELS')

# Charger les données
try:
    with open(os.path.join(DATA_DIR, 'intents.json'), 'r', encoding='utf-8') as f:
        intents = json.load(f)
    words = pickle.load(open(os.path.join(MODELS_DIR, 'vectorizer.pkl'), 'rb'))
    classes = pickle.load(open(os.path.join(MODELS_DIR, 'intent_classifier.pkl'), 'rb'))
    model = load_model(os.path.join(MODELS_DIR, 'train_model.h5'))
    print("✅ Modèle chargé avec succès")
except Exception as e:
    print(f"❌ Erreur lors du chargement du modèle: {e}")
    intents = {"intents": []}
    words = []
    classes = []
    model = None

# Initialiser SharePoint (optionnel, désactivé par défaut)
USE_SHAREPOINT = False
try:
    from API.sharepoint_connector import SharePointConnector
    sp_connector = SharePointConnector()
    USE_SHAREPOINT = True
    print("✅ SharePoint connecté")
except Exception as e:
    print(f"⚠️ SharePoint non disponible: {e}")
    sp_connector = None

def clean_up_sentence(sentence):
    """Nettoyer et lemmatiser une phrase"""
    sentence_words = nltk.word_tokenize(sentence)
    sentence_words = [lemmatizer.lemmatize(word.lower()) for word in sentence_words]
    return sentence_words

def bag_of_words(sentence):
    """Convertir une phrase en bag of words"""
    sentence_words = clean_up_sentence(sentence)
    bag = [0] * len(words)
    for w in sentence_words:
        for i, word in enumerate(words):
            if word == w:
                bag[i] = 1
    return np.array(bag)

def predict_class(sentence):
    """Prédire l'intention d'une phrase"""
    if model is None:
        return []
    
    bow = bag_of_words(sentence)
    res = model.predict(np.array([bow]), verbose=0)[0]
    ERROR_THRESHOLD = 0.25
    results = [[i, r] for i, r in enumerate(res) if r > ERROR_THRESHOLD]
    
    results.sort(key=lambda x: x[1], reverse=True)
    return_list = []
    for r in results:
        return_list.append({
            'intent': classes[r[0]], 
            'probability': str(r[1])
        })
    return return_list

def get_response(intents_list, intents_json, message):
    """Obtenir une réponse basée sur l'intention détectée"""
    if not intents_list:
        return "Je ne suis pas sûr de comprendre votre question. Pouvez-vous la reformuler ? 🤔\n\nJe peux vous aider sur SharePoint, Teams et OneDrive."
    
    tag = intents_list[0]['intent']
    confidence = float(intents_list[0]['probability'])
    
    # Si confiance faible, demander clarification
    if confidence < 0.5:
        return "Je ne suis pas certain de bien comprendre. Pouvez-vous préciser votre question ?"
    
    # Gestion spéciale pour les demandes de guides
    if tag == 'get_guide' and USE_SHAREPOINT:
        guides = sp_connector.get_user_guides()
        if guides:
            response = "📚 Voici les guides disponibles :\n\n"
            for guide in guides[:3]:
                response += f"📄 **{guide['title']}**\n"
                response += f"🔗 {guide['url']}\n\n"
            return response
        else:
            return "Je peux vous aider avec SharePoint, Teams et OneDrive. Que souhaitez-vous savoir ?"
    
    # Recherche dans SharePoint si pertinent
    if USE_SHAREPOINT and tag in ['sharepoint_usage', 'teams_usage', 'onedrive_usage']:
        faqs = sp_connector.get_faq_items()
        category = tag.replace('_usage', '').capitalize()
        for faq in faqs:
            if category.lower() in faq['category'].lower():
                return faq['answer']
    
    # Réponse par défaut depuis intents.json
    list_of_intents = intents_json['intents']
    for i in list_of_intents:
        if i['tag'] == tag:
            result = random.choice(i['responses'])
            return result
    
    return "Je ne suis pas sûr de comprendre. 🤔"

def chatbot_response(message):
    """Fonction principale pour obtenir une réponse du chatbot"""
    try:
        ints = predict_class(message)
        res = get_response(ints, intents, message)
        return res
    except Exception as e:
        print(f"Erreur chatbot: {e}")
        return "Désolé, une erreur s'est produite. Pouvez-vous reformuler votre question ?"

# Test de la fonction
if __name__ == "__main__":
    print("🤖 Chatbot M365 prêt!")
    print("Tapez 'quit' pour quitter\n")
    
    while True:
        message = input("Vous: ")
        if message.lower() == 'quit':
            break
        
        response = chatbot_response(message)
        print(f"Bot: {response}\n")