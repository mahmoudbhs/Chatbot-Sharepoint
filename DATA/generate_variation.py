import json
import random

def generate_variations(base_patterns):
    """Générer des variations de questions"""
    
    variations = []
    
    # Préfixes
    prefixes = ["", "Comment ", "Comment je peux ", "Comment faire pour ", 
                "De quelle manière ", "Quelle est la méthode pour "]
    
    # Suffixes
    suffixes = ["", " ?", " svp", " s'il vous plaît", " merci"]
    
    for pattern in base_patterns:
        for prefix in prefixes:
            for suffix in suffixes:
                variation = prefix + pattern.lower() + suffix
                variations.append(variation.strip())
    
    return list(set(variations))  # Retirer doublons

# Exemple d'utilisation
base_patterns = [
    "partager un fichier Teams",
    "envoyer un document Teams",
    "transférer un fichier Teams"
]

variations = generate_variations(base_patterns)
print(f"Généré {len(variations)} variations")
for v in variations[:10]:
    print(f"- {v}")