"""
Script de test du modèle de chatbot
Permet de tester le chatbot en mode console
"""

import sys
import os

# Ajouter le chemin parent pour importer chatbot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from API.chatbot import chatbot_response

def print_banner():
    """Afficher une bannière de bienvenue"""
    print("=" * 60)
    print("🤖  CHATBOT M365 - MODE TEST  🤖".center(60))
    print("=" * 60)
    print("\nBienvenue dans le chatbot M365!")
    print("Je peux vous aider avec SharePoint, Teams et OneDrive.")
    print("\nCommandes spéciales:")
    print("  • 'quit' ou 'exit' : Quitter le programme")
    print("  • 'clear' : Effacer l'écran")
    print("  • 'help' : Afficher l'aide")
    print("=" * 60)
    print()

def print_help():
    """Afficher l'aide"""
    print("\n📚 AIDE - Exemples de questions:")
    print("  • Comment utiliser SharePoint ?")
    print("  • Comment créer une réunion Teams ?")
    print("  • À quoi sert OneDrive ?")
    print("  • Montre-moi les guides disponibles")
    print("  • Comment partager un document ?")
    print()

def clear_screen():
    """Effacer l'écran"""
    os.system('cls' if os.name == 'nt' else 'clear')

def test_chatbot():
    """Fonction principale de test"""
    print_banner()
    
    conversation_count = 0
    
    while True:
        try:
            # Demander l'input utilisateur
            user_input = input("💬 Vous: ").strip()
            
            # Vérifier les commandes spéciales
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Au revoir! À bientôt!")
                print(f"📊 Total de messages: {conversation_count}")
                break
            
            elif user_input.lower() == 'clear':
                clear_screen()
                print_banner()
                continue
            
            elif user_input.lower() == 'help':
                print_help()
                continue
            
            elif not user_input:
                continue
            
            # Obtenir la réponse du chatbot
            response = chatbot_response(user_input)
            
            # Afficher la réponse
            print(f"\n🤖 Bot: {response}\n")
            print("-" * 60)
            
            conversation_count += 1
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Interruption détectée...")
            print("👋 Au revoir!")
            break
        
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            print("Veuillez réessayer.\n")

def run_batch_tests():
    """Exécuter une série de tests prédéfinis"""
    test_questions = [
        "Bonjour",
        "Comment utiliser SharePoint?",
        "Comment créer une réunion Teams?",
        "À quoi sert OneDrive?",
        "Montre-moi les guides",
        "Merci",
        "Au revoir"
    ]
    
    print("\n" + "=" * 60)
    print("🧪  TESTS AUTOMATIQUES  🧪".center(60))
    print("=" * 60 + "\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n[Test {i}/{len(test_questions)}]")
        print(f"💬 Question: {question}")
        
        try:
            response = chatbot_response(question)
            print(f"🤖 Réponse: {response}")
            print("✅ Test réussi")
        except Exception as e:
            print(f"❌ Test échoué: {e}")
        
        print("-" * 60)
    
    print("\n✨ Tests terminés!\n")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Tester le chatbot M365')
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Exécuter les tests automatiques'
    )
    parser.add_argument(
        '--message',
        type=str,
        help='Envoyer un message unique et quitter'
    )
    
    args = parser.parse_args()
    
    if args.batch:
        run_batch_tests()
    elif args.message:
        print(f"💬 Vous: {args.message}")
        response = chatbot_response(args.message)
        print(f"🤖 Bot: {response}")
    else:
        test_chatbot()