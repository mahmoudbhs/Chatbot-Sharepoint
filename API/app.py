from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sys
import os

# Ajouter le chemin parent pour importer chatbot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from API.chatbot import chatbot_response

app = Flask(__name__, 
            template_folder='../FRONTEND',
            static_folder='../FRONTEND')
CORS(app)

@app.route('/')
def home():
    """Page d'accueil du chatbot"""
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Endpoint pour les messages du chatbot"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'Message vide'}), 400
        
        # Obtenir la réponse du chatbot
        response = chatbot_response(message)
        
        return jsonify({
            'response': response,
            'status': 'success'
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Vérifier que l'API fonctionne"""
    return jsonify({
        'status': 'healthy',
        'message': 'Chatbot M365 is running'
    })

if __name__ == '__main__':
    print("🤖 Démarrage du chatbot M365...")
    print("📍 Accédez au chatbot sur: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)