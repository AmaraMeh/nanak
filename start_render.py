#!/usr/bin/env python3
"""
Script de démarrage optimisé pour Render.com
"""

import os
import sys
import logging
import asyncio
from main import ELearningBot

# Configuration du logging pour Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("render_startup")

async def main():
    """Fonction principale pour Render"""
    logger.info("🚀 Démarrage du bot eLearning sur Render.com")
    
    try:
        # Créer et démarrer le bot
        bot = ELearningBot()
        logger.info("✅ Bot créé avec succès")
        
        # Démarrer le bot
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {str(e)}")
        sys.exit(1)
    finally:
        if 'bot' in locals():
            bot.stop()
        logger.info("👋 Arrêt du bot terminé")

if __name__ == "__main__":
    asyncio.run(main())