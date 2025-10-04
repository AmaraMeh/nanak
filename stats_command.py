#!/usr/bin/env python3
"""
Script pour afficher les statistiques du bot
"""

import asyncio
import sys
from monitoring import BotMonitor
from telegram_notifier import TelegramNotifier
from config import Config

async def send_stats_report():
    """Envoyer un rapport de statistiques via Telegram"""
    monitor = BotMonitor()
    notifier = TelegramNotifier()
    
    try:
        # Obtenir le chat ID
        chat_id = await notifier.get_chat_id()
        if not chat_id:
            print("❌ Impossible d'obtenir le chat ID")
            print("Envoyez un message à votre bot pour obtenir votre chat ID")
            return False
        
        # Générer le rapport
        report = monitor.generate_report()
        
        # Envoyer le rapport
        await notifier.bot.send_message(
            chat_id=chat_id,
            text=f"<pre>{report}</pre>",
            parse_mode='HTML'
        )
        
        print("✅ Rapport de statistiques envoyé via Telegram")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi du rapport: {str(e)}")
        return False

def print_stats():
    """Afficher les statistiques dans le terminal"""
    monitor = BotMonitor()
    report = monitor.generate_report()
    print(report)

def reset_stats():
    """Réinitialiser les statistiques"""
    monitor = BotMonitor()
    monitor.reset_stats()
    print("✅ Statistiques réinitialisées")

def main():
    """Fonction principale"""
    if len(sys.argv) < 2:
        print("Usage: python stats_command.py [print|telegram|reset]")
        print("  print    - Afficher les statistiques dans le terminal")
        print("  telegram - Envoyer les statistiques via Telegram")
        print("  reset    - Réinitialiser les statistiques")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "print":
        print_stats()
    elif command == "telegram":
        asyncio.run(send_stats_report())
    elif command == "reset":
        reset_stats()
    else:
        print(f"❌ Commande inconnue: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()