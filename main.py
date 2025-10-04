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
        self.stop_requested = False
        self.initial_scan_completed_at = None
        # Mémoire du dernier contenu des cours pour les commandes interactives
        self.last_courses_content = {}
        # Lier le bot principal au notifier pour accès aux méthodes
        self.notifier.set_bot_ref(self)
        # Injection pour téléchargement fichier (doit être dans __init__)
        self.scraper.firebase_mgr = self.firebase
        
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
            # Sauvegarder en mémoire pour les commandes
            self.last_courses_content = current_content or {}
            
            if not current_content:
                self.logger.error("Aucun contenu récupéré")
                self.monitor.record_error("scan_failed", "Aucun contenu récupéré")
                return
            
            # Vérifier chaque cours
            for course_id, content in current_content.items():
                if self.stop_requested:
                    self.logger.info("Arrêt demandé: interruption du scan en cours")
                    break
                await self._check_single_course(course_id, content, is_initial_scan)
                # Après chaque département (cours) terminé lors du premier scan: message récap + envoi fichiers auto
                if is_initial_scan and not self.stop_requested:
                    try:
                        cname = self._get_course_name(course_id)
                        await self.notifier.send_department_complete_message(cname, course_id, content)
                        if Config.SEND_FILES_AS_DOCUMENTS:
                            await self.notifier.send_course_files(course_id, cname)
                    except Exception as e:
                        self.logger.warning(f"Erreur post-département {course_id}: {e}")
            
            if is_initial_scan and not self.stop_requested:
                self.initial_scan_completed_at = datetime.now()
                self.logger.info("✅ Premier scan complet terminé")
                # Envoyer résumé global
                try:
                    await self.notifier.send_initial_global_summary(self.last_courses_content)
                except Exception as e:
                    self.logger.warning(f"Envoi résumé global échoué: {e}")
            else:
                self.logger.info("Vérification terminée")
                # Si aucun changement sur ce cycle, notifier éventuellement
                if Config.SEND_NO_UPDATES_MESSAGE and not self.monitor.last_notifications_cycle():
                    try:
                        await self.notifier.send_no_updates_cycle_message()
                    except Exception as e:
                        self.logger.warning(f"Notification 'pas de mise à jour' échouée: {e}")
            
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
            # Mettre à jour le snapshot mémoire individuel
            self.last_courses_content[course_id] = current_content
            
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
        # Lancer boucle de commandes Telegram (polling)
        asyncio.create_task(self.notifier.command_loop())

        while self.running:
            schedule.run_pending()
            await asyncio.sleep(1)
    
    def stop(self):
        """Arrêter le bot"""
        self.logger.info("Arrêt du bot")
        self.running = False
        self.stop_requested = True
        self.scraper.close()
        self.notifier.stopped = True

    # ================= Méthodes utilitaires pour commandes =================
    def get_status(self) -> str:
        return (
            f"Bot actif: {'✅' if self.running else '❌'}\n"
            f"Espaces surveillés: {len(Config.MONITORED_SPACES)}\n"
            f"Intervalle: {Config.CHECK_INTERVAL_MINUTES} min\n"
            f"Dernier snapshot: {len(self.last_courses_content)} cours"
        )

    def list_courses(self) -> list:
        return [(space['id'], space['name']) for space in Config.MONITORED_SPACES]

    def get_course_snapshot(self, course_id: str):
        return self.last_courses_content.get(course_id)

    def trigger_manual_scan(self, course_id: str = None):
        if course_id:
            # Lancer scan spécifique (async detached)
            asyncio.create_task(self._manual_single_scan(course_id))
        else:
            asyncio.create_task(self.check_all_courses())

    async def _manual_single_scan(self, course_id: str):
        space = next((s for s in Config.MONITORED_SPACES if s['id'] == course_id), None)
        if not space:
            return
        content = self.scraper.get_course_content(space['url'], space['id'])
        if content:
            self.last_courses_content[course_id] = content
            old_content = self.firebase.get_course_content(course_id)
            changes = self.detector.detect_changes(old_content, content, False)
            if changes:
                await self.notifier.send_notification(space['name'], space['url'], changes, False)
            self.firebase.save_course_content(course_id, content)
            # Option: envoyer fichiers si activé
            if Config.SEND_FILES_AS_DOCUMENTS:
                await self.notifier.send_course_files(course_id, space['name'])
    
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