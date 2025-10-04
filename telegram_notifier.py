import logging
from telegram import Bot
from telegram.error import TelegramError
import asyncio
from config import Config

class TelegramNotifier:
    def __init__(self):
        self.bot = Bot(token=Config.TELEGRAM_TOKEN)
        self.logger = logging.getLogger(__name__)
        self.chat_id = None
    
    async def get_chat_id(self):
        """Obtenir l'ID du chat pour les messages privés"""
        try:
            updates = await self.bot.get_updates()
            if updates:
                # Utiliser le dernier chat qui a envoyé un message
                self.chat_id = updates[-1].message.chat_id
                self.logger.info(f"Chat ID récupéré: {self.chat_id}")
                return self.chat_id
            else:
                self.logger.warning("Aucune mise à jour trouvée. Envoyez un message au bot pour obtenir votre chat ID.")
                return None
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du chat ID: {str(e)}")
            return None
    
    async def send_notification(self, course_name: str, course_url: str, changes: list, is_initial_scan: bool = False):
        """Envoyer une notification avec les changements détectés"""
        try:
            if not self.chat_id:
                await self.get_chat_id()
            
            if not self.chat_id:
                self.logger.error("Impossible d'envoyer la notification: chat ID non disponible")
                return False
            
            # Pour le premier scan, envoyer un message groupé pour éviter le spam
            if is_initial_scan and len(changes) > 10:
                await self._send_grouped_initial_scan(course_name, course_url, changes)
            else:
                # Construire le message normal
                message = self._build_message(course_name, course_url, changes, is_initial_scan)
                
                # Envoyer le message
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            
            self.logger.info(f"Notification envoyée pour le cours: {course_name}")
            return True
            
        except TelegramError as e:
            self.logger.error(f"Erreur Telegram lors de l'envoi de la notification: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi de la notification: {str(e)}")
            return False
    
    async def _send_grouped_initial_scan(self, course_name: str, course_url: str, changes: list):
        """Envoyer un scan initial groupé pour éviter le spam"""
        # Message de début
        start_message = f"🔍 <b>Premier scan complet</b>\n\n"
        start_message += f"📚 <b>Cours:</b> {course_name}\n"
        start_message += f"🔗 <b>Lien:</b> <a href='{course_url}'>Accéder au cours</a>\n\n"
        start_message += f"📊 <b>Contenu existant trouvé:</b> {len(changes)} éléments\n\n"
        start_message += "⏳ <i>Extraction en cours...</i>"
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=start_message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        # Grouper les changements par type
        grouped_changes = self._group_changes_by_type(changes)
        
        # Envoyer un résumé groupé
        summary_message = f"📋 <b>Résumé du contenu existant</b>\n\n"
        
        for change_type, items in grouped_changes.items():
            if items:
                summary_message += f"<b>{self._get_type_emoji(change_type)} {self._get_type_name(change_type)}:</b> {len(items)}\n"
        
        summary_message += f"\n⏰ <i>Scan terminé le {self._get_current_time()}</i>"
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=summary_message,
            parse_mode='HTML'
        )
    
    def _group_changes_by_type(self, changes: list) -> dict:
        """Grouper les changements par type"""
        grouped = {}
        for change in changes:
            change_type = change.get('type', 'unknown')
            if change_type not in grouped:
                grouped[change_type] = []
            grouped[change_type].append(change)
        return grouped
    
    def _get_type_emoji(self, change_type: str) -> str:
        """Obtenir l'emoji pour un type de changement"""
        emoji_map = {
            'existing_section': '📂',
            'existing_activity': '📋',
            'existing_resource': '📚',
            'existing_file': '📄',
            'section_added': '➕',
            'section_removed': '➖',
            'activity_added': '➕',
            'activity_removed': '➖',
            'resource_added': '➕',
            'resource_removed': '➖',
            'file_added': '📁',
            'file_removed': '🗑️',
            'activity_description_changed': '✏️'
        }
        return emoji_map.get(change_type, '📝')
    
    def _get_type_name(self, change_type: str) -> str:
        """Obtenir le nom lisible pour un type de changement"""
        name_map = {
            'existing_section': 'Sections existantes',
            'existing_activity': 'Activités existantes',
            'existing_resource': 'Ressources existantes',
            'existing_file': 'Fichiers existants',
            'section_added': 'Nouvelles sections',
            'section_removed': 'Sections supprimées',
            'activity_added': 'Nouvelles activités',
            'activity_removed': 'Activités supprimées',
            'resource_added': 'Nouvelles ressources',
            'resource_removed': 'Ressources supprimées',
            'file_added': 'Nouveaux fichiers',
            'file_removed': 'Fichiers supprimés',
            'activity_description_changed': 'Descriptions modifiées'
        }
        return name_map.get(change_type, 'Autres')
    
    def _build_message(self, course_name: str, course_url: str, changes: list, is_initial_scan: bool = False) -> str:
        """Construire le message de notification"""
        if is_initial_scan:
            message = f"🔍 <b>Premier scan du cours</b>\n\n"
        else:
            message = f"🔔 <b>Mise à jour détectée</b>\n\n"
        
        message += f"📚 <b>Cours:</b> {course_name}\n"
        message += f"🔗 <b>Lien:</b> <a href='{course_url}'>Accéder au cours</a>\n\n"
        
        message += f"📋 <b>Changements détectés ({len(changes)}):</b>\n\n"
        
        for i, change in enumerate(changes, 1):
            message += f"{i}. <b>{change['message']}</b>\n"
            
            if 'details' in change:
                message += f"   📝 {change['details']}\n"
            
            # Ajouter des emojis selon le type de changement
            emoji = self._get_type_emoji(change.get('type', 'unknown'))
            message += f"   {emoji}\n"
            
            message += "\n"
        
        message += f"⏰ <i>Détecté le {self._get_current_time()}</i>"
        
        return message
    
    def _get_current_time(self) -> str:
        """Obtenir l'heure actuelle formatée"""
        from datetime import datetime
        return datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
    
    async def send_startup_message(self, monitor=None):
        """Envoyer un message de démarrage du bot"""
        try:
            if not self.chat_id:
                await self.get_chat_id()
            
            if not self.chat_id:
                return False
            
            message = "🤖 <b>Bot eLearning Notifier démarré</b>\n\n"
            message += "✅ Surveillance active des espaces d'affichage\n"
            message += f"⏱️ Vérification toutes les {Config.CHECK_INTERVAL_MINUTES} minutes\n"
            message += f"📚 {len(Config.MONITORED_SPACES)} espaces surveillés\n\n"
            
            # Ajouter les statistiques si disponibles
            if monitor:
                stats = monitor.get_summary_stats()
                if stats['total_scans'] > 0:
                    message += f"📊 Statistiques:\n"
                    message += f"• Temps de fonctionnement: {stats['uptime']}\n"
                    message += f"• Total des scans: {stats['total_scans']}\n"
                    message += f"• Taux de succès: {stats['success_rate']}\n"
                    message += f"• Notifications envoyées: {stats['total_notifications']}\n\n"
            
            message += "🔔 Vous recevrez une notification dès qu'un changement sera détecté !\n\n"
            message += "🔍 <b>Premier scan en cours...</b>"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            self.logger.info("Message de démarrage envoyé")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi du message de démarrage: {str(e)}")
            return False
    
    async def send_error_message(self, error_message: str):
        """Envoyer un message d'erreur"""
        try:
            if not self.chat_id:
                await self.get_chat_id()
            
            if not self.chat_id:
                return False
            
            message = f"❌ <b>Erreur du Bot</b>\n\n{error_message}"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            self.logger.info("Message d'erreur envoyé")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi du message d'erreur: {str(e)}")
            return False