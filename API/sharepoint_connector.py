class SharePointConnector:
    def __init__(self):
        print(" Connecteur SharePoint initialisé (Mode Simulation)")

    def get_user_guides(self):
        """Simule la récupération de guides depuis SharePoint"""
        return [
            {"title": "Guide de démarrage Teams", "url": "https://support.microsoft.com/fr-fr/teams"},
            {"title": "Utiliser OneDrive", "url": "https://support.microsoft.com/fr-fr/onedrive"}
        ]

    def get_faq_items(self):
        """Simule la récupération de la FAQ"""
        return []