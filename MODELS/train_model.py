import json
import numpy as np
import pickle
import nltk
from nltk.stem import WordNetLemmatizer
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.optimizers import SGD
import random
import os
import nltk
# Ajoute ces lignes pour télécharger les ressources manquantes
nltk.download('punkt')
nltk.download('punkt_tab') # C'est celle qui manque sur ton image !
nltk.download('wordnet')

# Initialisation
lemmatizer = WordNetLemmatizer()
nltk.download('punkt')
nltk.download('wordnet')

# Chemins
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTENTS_PATH = os.path.join(BASE_DIR, 'DATA', 'intents.json')
RESPONSES_PATH = os.path.join(BASE_DIR, 'DATA', 'responses.json')
TRAINING_DATA_PATH = os.path.join(BASE_DIR, 'DATA', 'training_data.json')
MODELS_DIR = os.path.join(BASE_DIR, 'MODELS')

# 1. Charger les données
with open(INTENTS_PATH, 'r', encoding='utf-8') as file:
    intents = json.load(file)

words = []
classes = []
documents = []
ignore_letters = ['!', '?', ',', '.']

# 2. Prétraitement
for intent in intents['intents']:
    for pattern in intent['patterns']:
        word_list = nltk.word_tokenize(pattern)
        words.extend(word_list)
        documents.append((word_list, intent['tag']))
        if intent['tag'] not in classes:
            classes.append(intent['tag'])

words = [lemmatizer.lemmatize(w.lower()) for w in words if w not in ignore_letters]
words = sorted(list(set(words)))
classes = sorted(list(set(classes)))

# Sauvegarder les structures de données (PKL)
pickle.dump(words, open(os.path.join(MODELS_DIR, 'vectorizer.pkl'), 'wb'))
pickle.dump(classes, open(os.path.join(MODELS_DIR, 'intent_classifier.pkl'), 'wb'))

# 3. Créer les données d'entraînement
training = []
output_empty = [0] * len(classes)

for doc in documents:
    bag = []
    word_patterns = doc[0]
    word_patterns = [lemmatizer.lemmatize(word.lower()) for word in word_patterns]
    for word in words:
        bag.append(1) if word in word_patterns else bag.append(0)

    output_row = list(output_empty)
    output_row[classes.index(doc[1])] = 1
    training.append([bag, output_row])

random.shuffle(training)
training = np.array(training, dtype=object)

train_x = list(training[:, 0])
train_y = list(training[:, 1])

# 4. Construire le modèle
model = Sequential()
model.add(Dense(128, input_shape=(len(train_x[0]),), activation='relu'))
model.add(Dropout(0.5))
model.add(Dense(64, activation='relu'))
model.add(Dropout(0.5))
model.add(Dense(len(train_y[0]), activation='softmax'))

# Compiler le modèle
sgd = SGD(learning_rate=0.01, momentum=0.9, nesterov=True)
model.compile(loss='categorical_crossentropy', optimizer=sgd, metrics=['accuracy'])

# 5. Entraîner et Sauvegarder (H5)
model.fit(np.array(train_x), np.array(train_y), epochs=200, batch_size=5, verbose=1)
model.save(os.path.join(MODELS_DIR, 'train_model.h5'))

print("\n✅ Modèle entraîné avec succès !")