#!/usr/bin/env python3
"""
Script de démarrage simplifié du bot
"""

import asyncio
import sys
import os
from main import ELearningBot

# Import Config at the top level
from config import Config

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
    """Fonction principale avec boucle de résilience pour éviter arrêt prématuré"""
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

    restart_count = 0
    MAX_RESTARTS = 50
    BACKOFF_SECONDS = 5

    while True:
        bot = ELearningBot()
        try:
            await bot.start()  # ne devrait pas retourner tant qu'on n'a pas demandé stop
            if bot.stop_requested:
                print("🛑 Arrêt demandé manuellement — sortie propre")
                break
            # Si on arrive ici sans stop explicite, on va relancer
            print("⚠️ start() a terminé sans demande d'arrêt. Redémarrage automatique...")
        except KeyboardInterrupt:
            print("\n🛑 Arrêt demandé par l'utilisateur (CTRL+C)")
            bot.stop_requested = True
            bot.stop()
            break
        except Exception as e:
            print(f"❌ Erreur runtime: {e}. Redémarrage dans {BACKOFF_SECONDS}s...")
        finally:
            bot.stop()
            print("🔁 Cycle bot terminé")

        restart_count += 1
        if restart_count >= MAX_RESTARTS:
            print("❌ Nombre maximal de redémarrages atteint. Abandon.")
            break
        await asyncio.sleep(BACKOFF_SECONDS)

    print("👋 Bot arrêté")

if __name__ == "__main__":
    asyncio.run(main())