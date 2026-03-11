import os
import random
import json
import pickle
import numpy as np
import nltk
from nltk.stem import WordNetLemmatizer
from tensorflow.keras.models import load_model
from API.sharepoint_connector import SharePointConnector

lemmatizer = WordNetLemmatizer()

# --- LES LIGNES QU'IL TE MANQUAIT SONT ICI 👇 ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'DATA')
MODELS_DIR = os.path.join(BASE_DIR, 'MODELS')
# -----------------------------------------------

# Chargement avec encodage UTF-8 et les BONS noms de fichiers
try:
    intents_path = os.path.join(DATA_DIR, 'intents.json')
    intents = json.loads(open(intents_path, encoding='utf-8').read())
    
    # Correction : on cherche vectorizer.pkl et intent_classifier.pkl
    words = pickle.load(open(os.path.join(MODELS_DIR, 'vectorizer.pkl'), 'rb'))
    classes = pickle.load(open(os.path.join(MODELS_DIR, 'intent_classifier.pkl'), 'rb'))
    model = load_model(os.path.join(MODELS_DIR, 'train_model.h5'))
    
    print("✅ Modèles du chatbot chargés avec succès !")
except Exception as e:
    print(f"❌ Erreur lors du chargement des modèles : {e}")

# Initialiser SharePoint
sp_connector = SharePointConnector()

def clean_up_sentence(sentence):
    sentence_words = nltk.word_tokenize(sentence)
    sentence_words = [lemmatizer.lemmatize(word.lower()) for word in sentence_words]
    return sentence_words

def bag_of_words(sentence):
    sentence_words = clean_up_sentence(sentence)
    bag = [0] * len(words)
    for w in sentence_words:
        for i, word in enumerate(words):
            if word == w:
                bag[i] = 1
    return np.array(bag)

def predict_class(sentence):
    bow = bag_of_words(sentence)
    # On ajoute verbose=0 pour cacher les logs de prédiction
    res = model.predict(np.array([bow]), verbose=0)[0]
    ERROR_THRESHOLD = 0.25
    results = [[i, r] for i, r in enumerate(res) if r > ERROR_THRESHOLD]
    
    results.sort(key=lambda x: x[1], reverse=True)
    return_list = []
    for r in results:
        return_list.append({'intent': classes[r[0]], 'probability': str(r[1])})
    return return_list

def get_response(intents_list, intents_json, message):
    if not intents_list:
        return "Je ne suis pas sûr de comprendre. Pouvez-vous reformuler ?"
    
    tag = intents_list[0]['intent']
    
    # Gestion spéciale pour les demandes de guides
    if tag == 'get_guide':
        guides = sp_connector.get_user_guides()
        if guides:
            response = "Voici les guides disponibles :\n\n"
            for guide in guides[:3]:  # Limiter à 3 guides
                response += f" {guide['title']}\n{guide['url']}\n\n"
            return response
        else:
            return "Désolé, je n'ai pas pu récupérer les guides pour le moment."
    
    # Recherche dans SharePoint si pertinent
    if tag in ['sharepoint_usage', 'teams_usage', 'onedrive_usage']:
        # Chercher dans la FAQ SharePoint
        faqs = sp_connector.get_faq_items()
        for faq in faqs:
            if tag.replace('_usage', '') in faq['category'].lower():
                return faq['answer']
    
    # Réponse par défaut depuis intents.json
    list_of_intents = intents_json['intents']
    for i in list_of_intents:
        if i['tag'] == tag:
            result = random.choice(i['responses'])
            return result
    
    return "Je ne suis pas sûr de comprendre."

def chatbot_response(message):
    try:
        ints = predict_class(message)
        res = get_response(ints, intents, message)
        return res
    except Exception as e:
        print(f"Erreur interne lors de la prédiction: {e}")
        return "Désolé, mon cerveau a eu un petit bug en essayant de répondre. Pouvez-vous réessayer ?"