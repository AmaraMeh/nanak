#!/usr/bin/env python3
"""
Script de démarrage simplifié du bot
"""

import asyncio
import sys
import os
from main import ELearningBot

def check_requirements():
    """Vérifier que tous les prérequis sont installés"""
    try:
        import requests
        import telegram
        import firebase_admin
        import schedule
        import bs4
        print("✅ Toutes les dépendances sont installées")
        return True
    except ImportError as e:
        print(f"❌ Dépendance manquante: {e}")
        print("Veuillez installer les dépendances avec: pip install -r requirements.txt")
        return False

def check_config():
    """Vérifier la configuration"""
    from config import Config
    
    if not Config.USERNAME or not Config.PASSWORD:
        print("❌ Identifiants eLearning manquants")
        print("Veuillez configurer ELEARNING_USERNAME et ELEARNING_PASSWORD dans le fichier .env")
        return False
    
    if not Config.TELEGRAM_TOKEN:
        print("❌ Token Telegram manquant")
        print("Veuillez configurer TELEGRAM_TOKEN dans le fichier .env")
        return False
    
    print("✅ Configuration vérifiée")
    return True

async def main():
    """Fonction principale"""
    print("🤖 Démarrage du Bot eLearning Notifier")
    print("=" * 50)
    
    # Vérifications préliminaires
    if not check_requirements():
        sys.exit(1)
    
    if not check_config():
        sys.exit(1)
    
    print(f"📚 Surveillance de {len(Config.MONITORED_SPACES)} espaces d'affichage")
    print(f"⏱️ Vérification toutes les {Config.CHECK_INTERVAL_MINUTES} minutes")
    print("=" * 50)
    
    # Créer et démarrer le bot
    bot = ELearningBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par l'utilisateur")
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
    finally:
        bot.stop()
        print("👋 Bot arrêté")

if __name__ == "__main__":
    asyncio.run(main())