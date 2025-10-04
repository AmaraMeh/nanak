#!/usr/bin/env python3
"""
Bot de surveillance automatique des espaces d'affichage eLearning
Université de Béjaïa
"""

import asyncio
import logging
import schedule
import time
import signal
import sys
from datetime import datetime
from elearning_scraper import ELearningScraper
from firebase_manager import FirebaseManager
from change_detector import ChangeDetector
from telegram_notifier import TelegramNotifier
from monitoring import BotMonitor
from config import Config

class ELearningBot:
    def __init__(self):
        self.scraper = ELearningScraper()
        self.firebase = FirebaseManager()
        self.detector = ChangeDetector()
        self.notifier = TelegramNotifier()
        self.monitor = BotMonitor()
        self.logger = self._setup_logging()
        self.running = False
        
    def _setup_logging(self):
        """Configurer le système de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('bot.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger(__name__)
    
    async def check_all_courses(self, is_initial_scan: bool = False):
        """Vérifier tous les cours surveillés"""
        if is_initial_scan:
            self.logger.info("🔍 Début du premier scan complet - Extraction de tout le contenu existant")
        else:
            self.logger.info("Début de la vérification des cours")
        
        # Enregistrer le début du scan
        self.monitor.record_scan_start()
        
        try:
            # Récupérer le contenu actuel de tous les cours
            current_content = self.scraper.get_all_courses_content()
            
            if not current_content:
                self.logger.error("Aucun contenu récupéré")
                self.monitor.record_error("scan_failed", "Aucun contenu récupéré")
                return
            
            # Vérifier chaque cours
            for course_id, content in current_content.items():
                await self._check_single_course(course_id, content, is_initial_scan)
            
            if is_initial_scan:
                self.logger.info("✅ Premier scan complet terminé")
            else:
                self.logger.info("Vérification terminée")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification: {str(e)}")
            self.monitor.record_error("scan_error", str(e))
            await self.notifier.send_error_message(f"Erreur lors de la vérification: {str(e)}")
        
        finally:
            # Fermer le driver
            self.scraper.close()
    
    async def _check_single_course(self, course_id: str, current_content: dict, is_initial_scan: bool = False):
        """Vérifier un cours spécifique"""
        course_name = self._get_course_name(course_id)
        
        try:
            # Récupérer le contenu précédent
            old_content = self.firebase.get_course_content(course_id)
            
            # Détecter les changements
            changes = self.detector.detect_changes(old_content, current_content, is_initial_scan)
            
            if changes:
                course_url = self._get_course_url(course_id)
                
                # Envoyer la notification
                await self.notifier.send_notification(course_name, course_url, changes, is_initial_scan)
                
                # Enregistrer la notification
                self.monitor.record_notification(course_id, len(changes))
                
                # Sauvegarder le log des changements
                self.firebase.save_changes_log(course_id, changes)
                
                if is_initial_scan:
                    self.logger.info(f"Premier scan terminé pour {course_name}: {len(changes)} éléments trouvés")
                else:
                    self.logger.info(f"Changements détectés pour {course_name}: {len(changes)} changements")
            
            # Compter les éléments trouvés
            total_items = sum(len(section.get('activities', [])) + len(section.get('resources', [])) 
                             for section in current_content.get('sections', []))
            
            # Enregistrer le résultat du scan
            self.monitor.record_scan_result(course_id, course_name, True, total_items)
            
            # Sauvegarder le nouveau contenu
            self.firebase.save_course_content(course_id, current_content)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification du cours {course_id}: {str(e)}")
            self.monitor.record_error("course_scan_error", str(e), course_id)
            self.monitor.record_scan_result(course_id, course_name, False)
    
    def _get_course_name(self, course_id: str) -> str:
        """Obtenir le nom d'un cours par son ID"""
        for space in Config.MONITORED_SPACES:
            if space['id'] == course_id:
                return space['name']
        return f"Cours {course_id}"
    
    def _get_course_url(self, course_id: str) -> str:
        """Obtenir l'URL d'un cours par son ID"""
        for space in Config.MONITORED_SPACES:
            if space['id'] == course_id:
                return space['url']
        return Config.ELEARNING_URL
    
    async def start(self):
        """Démarrer le bot"""
        self.logger.info("Démarrage du bot eLearning Notifier")
        self.running = True
        
        # Envoyer le message de démarrage
        await self.notifier.send_startup_message(self.monitor)
        
        # Planifier la vérification périodique
        schedule.every(Config.CHECK_INTERVAL_MINUTES).minutes.do(
            lambda: asyncio.create_task(self.check_all_courses())
        )
        
        # Première vérification immédiate (scan complet)
        await self.check_all_courses(is_initial_scan=True)
        
        # Boucle principale
        while self.running:
            schedule.run_pending()
            await asyncio.sleep(1)
    
    def stop(self):
        """Arrêter le bot"""
        self.logger.info("Arrêt du bot")
        self.running = False
        self.scraper.close()
    
    def signal_handler(self, signum, frame):
        """Gestionnaire de signaux pour l'arrêt propre"""
        self.logger.info(f"Signal {signum} reçu, arrêt du bot...")
        self.stop()
        sys.exit(0)

def main():
    """Fonction principale"""
    bot = ELearningBot()
    
    # Gestionnaire de signaux
    signal.signal(signal.SIGINT, bot.signal_handler)
    signal.signal(signal.SIGTERM, bot.signal_handler)
    
    try:
        # Démarrer le bot
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        bot.logger.info("Arrêt demandé par l'utilisateur")
    except Exception as e:
        bot.logger.error(f"Erreur fatale: {str(e)}")
    finally:
        bot.stop()

if __name__ == "__main__":
    main()