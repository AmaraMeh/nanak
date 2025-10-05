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
        # Indique si un big scan complet forcé doit ignorer suppression initiale
        self.force_full_initial = False
        # Par défaut on ne télécharge PAS les fichiers (seulement en bigscan)
        self.scraper.enable_file_download = False
        # Mémoire du dernier contenu des cours pour les commandes interactives
        self.last_courses_content = {}
        # Lier le bot principal au notifier pour accès aux méthodes
        self.notifier.set_bot_ref(self)
        # Injection pour téléchargement fichier (doit être dans __init__)
        self.scraper.firebase_mgr = self.firebase
        # Contexte bigscan courant
        self.current_bigscan = None
        
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
        """Vérifier tous les cours surveillés
        is_initial_scan: indique intention de faire un scan initial; sera converti en scan incrémental
        si des snapshots existent déjà (redémarrage) et que force_full_initial n'est pas activé.
        """
        import time as _t
        scan_started_at = _t.time()
        # Détection redémarrage: si on a déjà des contenus en base, ne pas re-spammer inventaire
        if is_initial_scan and not self.force_full_initial:
            # Vérifier si au moins un cours a déjà un contenu sauvegardé
            already_has_data = any(self.firebase.get_course_content(space['id']) for space in Config.MONITORED_SPACES)
            if already_has_data:
                self.logger.info("♻️ Redémarrage détecté: le 'premier' scan sera traité comme incrémental pour éviter le spam")
                is_initial_scan = False

        if is_initial_scan:
            self.logger.info("🔍 Début du premier scan complet - Extraction de tout le contenu existant")
            if self.force_full_initial:
                # Audit début bigscan manuel
                self.current_bigscan = {
                    'start': datetime.now().isoformat(),
                    'files_sent': set(),
                    'courses': [],
                    'total_courses': len(Config.MONITORED_SPACES),
                    'course_times': [],
                    'milestones_sent': set(),
                    'course_file_counts': {}
                }
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
            
            # Préparer collecte cycle (hors initial)
            if not is_initial_scan:
                self.no_update_courses_cycle = []
                self.changed_courses_cycle = []

            # Vérifier chaque cours
            for course_id, content in current_content.items():
                if self.stop_requested:
                    self.logger.info("Arrêt demandé: interruption du scan en cours")
                    break
                # Marquer début traitement cours pour temps
                import time as _t
                if self.current_bigscan is not None:
                    self.current_bigscan['last_course_start'] = _t.time()
                await self._check_single_course(course_id, content, is_initial_scan)
                # Après chaque département (cours) terminé lors du premier scan: message récap (+ fichiers uniquement si bigscan)
                if is_initial_scan and not self.stop_requested:
                    try:
                        cname = self._get_course_name(course_id)
                        await self.notifier.send_department_complete_message(cname, course_id, content)
                        if self.scraper.enable_file_download and Config.SEND_FILES_AS_DOCUMENTS:
                            await self.notifier.send_course_files(course_id, cname)
                            if self.current_bigscan is not None:
                                self.current_bigscan['courses'].append(course_id)
                                # Durée cours
                                try:
                                    start_ct = self.current_bigscan.get('last_course_start')
                                    if start_ct:
                                        self.current_bigscan['course_times'].append(_t.time() - start_ct)
                                except Exception:
                                    pass
                                # Auto progress milestone
                                try:
                                    done = len(self.current_bigscan['courses'])
                                    total = self.current_bigscan.get('total_courses', 1)
                                    percent = (done / total) * 100 if total else 0
                                    for milestone in (10,25,50,75,90):
                                        if percent >= milestone and milestone not in self.current_bigscan['milestones_sent']:
                                            self.current_bigscan['milestones_sent'].add(milestone)
                                            try:
                                                await self.notifier.send_bigscan_progress(self.current_bigscan, auto=True)
                                            except Exception:
                                                pass
                                except Exception as _pgerr:
                                    self.logger.debug(f"Progress milestone err: {_pgerr}")
                                # Compter fichiers du cours (structure) pour stats finales
                                try:
                                    file_count = 0
                                    for s in content.get('sections', []):
                                        for a in s.get('activities', []):
                                            file_count += len(a.get('files', []))
                                        for r in s.get('resources', []):
                                            file_count += len(r.get('files', []))
                                    self.current_bigscan['course_file_counts'][course_id] = file_count
                                except Exception:
                                    pass
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
                # Reset flag big scan
                self.force_full_initial = False
                # Audit fin bigscan si ctx
                if self.current_bigscan is not None:
                    self.current_bigscan['end'] = datetime.now().isoformat()
                    self.firebase.save_audit_event('bigscan', {
                        'start': self.current_bigscan.get('start'),
                        'end': self.current_bigscan.get('end'),
                        'courses': self.current_bigscan.get('courses'),
                        'files_sent_count': len(self.current_bigscan.get('files_sent', []))
                    })
                    # Résumé fichiers
                    if Config.SEND_FILES_AS_DOCUMENTS:
                        try:
                            await self.notifier.send_bigscan_files_summary(self.current_bigscan)
                        except Exception as e:
                            self.logger.warning(f"Résumé fichiers bigscan échoué: {e}")
                # Message final de complétion initiale
                try:
                    elapsed = _t.time() - scan_started_at
                    await self.notifier.send_initial_completion_message(elapsed, len(self.last_courses_content))
                except Exception as e:
                    self.logger.warning(f"Message fin initial échoué: {e}")
                    self.current_bigscan = None
            else:
                self.logger.info("Vérification terminée")
                # Si aucun changement sur ce cycle, notifier éventuellement
                if not is_initial_scan and Config.SEND_NO_UPDATES_MESSAGE:
                    # Envoyer résumé global no-update + updates
                    try:
                        await self.notifier.send_cycle_update_summary(
                            getattr(self, 'changed_courses_cycle', []),
                            getattr(self, 'no_update_courses_cycle', [])
                        )
                    except Exception as e:
                        self.logger.warning(f"Résumé cycle échoué: {e}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification: {str(e)}")
            self.monitor.record_error("scan_error", str(e))
            await self.notifier.send_error_message(f"Erreur lors de la vérification: {str(e)}")
        
        finally:
            # Ne pas fermer la session HTTP pour permettre réutilisation
            pass
    
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

                # Si nouveaux fichiers détectés et option active, tenter téléchargement + envoi ciblé
                if not is_initial_scan and Config.SEND_FILES_AS_DOCUMENTS:
                    new_files = [c for c in changes if c.get('type') == 'file_added']
                    if new_files:
                        try:
                            # Activer temporairement le download
                            prev = self.scraper.enable_file_download
                            self.scraper.enable_file_download = True
                            # Re-scraper uniquement ce cours pour récupérer et télécharger les fichiers
                            space = next((s for s in Config.MONITORED_SPACES if s['id']==course_id), None)
                            if space:
                                refreshed = self.scraper.get_course_content(space['url'], space['id'])
                                if refreshed:
                                    # Sauvegarder snapshot mis à jour (avec fichiers téléchargés)
                                    self.firebase.save_course_content(course_id, refreshed)
                                    self.last_courses_content[course_id] = refreshed
                                    await self.notifier.send_course_files(course_id, course_name)
                            self.scraper.enable_file_download = prev
                        except Exception as send_file_err:
                            self.logger.warning(f"Envoi fichiers nouveaux échoué {course_id}: {send_file_err}")
                
                # Enregistrer la notification
                self.monitor.record_notification(course_id, len(changes))
                
                # Sauvegarder le log des changements
                self.firebase.save_changes_log(course_id, changes)
                
                if is_initial_scan:
                    self.logger.info(f"Premier scan terminé pour {course_name}: {len(changes)} éléments trouvés")
                else:
                    self.logger.info(f"Changements détectés pour {course_name}: {len(changes)} changements")
            else:
                # Aucun changement détecté
                if not is_initial_scan and Config.SEND_NO_UPDATES_MESSAGE:
                    # Accumuler pour résumé global de cycle
                    self.no_update_courses_cycle.append((course_id, course_name))
            if changes and not is_initial_scan and Config.SEND_NO_UPDATES_MESSAGE:
                self.changed_courses_cycle.append((course_id, course_name))
            
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

        # Déterminer si c'est le tout premier run (aucun snapshot persistant)
        first_run = not any(self.firebase.get_course_content(space['id']) for space in Config.MONITORED_SPACES)
        if first_run:
            self.logger.info("🟢 Aucune donnée trouvée: exécution du BIG SCAN initial")
            self.force_full_initial = True
            # Activer téléchargement des fichiers seulement pendant ce big scan initial
            self.scraper.enable_file_download = Config.SEND_FILES_AS_DOCUMENTS
            await self.check_all_courses(is_initial_scan=True)
            # Après big scan initial: désactiver téléchargement automatique
            self.scraper.enable_file_download = False
        else:
            # Baseline silencieuse pour préparer les diffs sans spammer
            self.scraper.enable_file_download = False
            await self.quick_baseline()
        
        # Boucle principale
        # Lancer boucle de commandes Telegram (polling)
        asyncio.create_task(self.notifier.command_loop())

        while self.running and not self.stop_requested:
            try:
                schedule.run_pending()
                await asyncio.sleep(1)
            except Exception as loop_err:
                self.logger.error(f"Boucle principale erreur: {loop_err}")
                await asyncio.sleep(3)
                # Continuer sauf si arrêt demandé
                continue
    
    def stop(self):
        """Arrêter le bot"""
        self.logger.info("Arrêt du bot")
        self.running = False
        self.stop_requested = True
        self.scraper.close()
        self.notifier.stopped = True

    # ================= Méthodes utilitaires pour commandes =================
    def get_status(self) -> str:
        # Construire info scans
        initial_ts = self.initial_scan_completed_at.strftime('%d/%m %H:%M:%S') if self.initial_scan_completed_at else '—'
        firebase_status = '✅' if getattr(self.firebase, 'db', None) else '⚠️(local)'
        return (
            f"Bot actif: {'✅' if self.running else '❌'}\n"
            f"Firebase: {firebase_status}\n"
            f"Espaces surveillés: {len(Config.MONITORED_SPACES)}\n"
            f"Intervalle: {Config.CHECK_INTERVAL_MINUTES} min\n"
            f"Scan initial terminé: {initial_ts}\n"
            f"Snapshots en mémoire: {len(self.last_courses_content)} cours"
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

    def trigger_big_scan(self):
        """Forcer un inventaire complet comme si c'était le premier (utilisé par /bigscan)."""
        self.force_full_initial = True
        # Activer téléchargement fichiers seulement pour ce bigscan
        self.scraper.enable_file_download = Config.SEND_FILES_AS_DOCUMENTS
        async def _run_big():
            await self.check_all_courses(is_initial_scan=True)
            # Après bigscan, désactiver
            self.scraper.enable_file_download = False
        asyncio.create_task(_run_big())

    async def quick_baseline(self):
        """Effectuer un scan baseline silencieux: capture l'état sans notifications.
        Objectif: éviter le flood initial tout en permettant les diffs incrémentaux ensuite.
        """
        self.logger.info("⚡ Baseline silencieuse en cours (aucune notification envoyée)")
        try:
            snapshot = self.scraper.get_all_courses_content()
            if not snapshot:
                self.logger.warning("Baseline: aucun contenu récupéré")
                return
            for course_id, content in snapshot.items():
                self.firebase.save_course_content(course_id, content)
                self.last_courses_content[course_id] = content
            self.logger.info("Baseline terminée: état initial mémorisé.")
        except Exception as e:
            self.logger.error(f"Erreur baseline silencieuse: {e}")


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