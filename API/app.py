from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sys
import os

# Ajouter le chemin parent pour importer le chatbot sans erreur
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from API.chatbot import chatbot_response

app = Flask(__name__, 
            template_folder='../FRONTEND',
            static_folder='../FRONTEND',
            static_url_path='') # Permet d'accéder aux fichiers statiques à la racine
CORS(app)  # Activer CORS pour toutes les routes

@app.route('/')
def home():
    """Page d'accueil du chatbot"""
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Endpoint pour recevoir et traiter les messages"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'Message vide'}), 400
        
        # Obtenir la réponse de l'IA
        response = chatbot_response(message)
        
        return jsonify({
            'response': response,
            'status': 'success'
        })
    
    except Exception as e:
        print(f"Erreur API: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Démarrage de l'API Assistant M365...")
    print(" Accédez au chatbot sur : http://localhost:5000")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)