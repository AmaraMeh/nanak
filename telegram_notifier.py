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
    
    async def send_notification(self, course_name: str, course_url: str, changes: list):
        """Envoyer une notification avec les changements détectés"""
        try:
            if not self.chat_id:
                await self.get_chat_id()
            
            if not self.chat_id:
                self.logger.error("Impossible d'envoyer la notification: chat ID non disponible")
                return False
            
            # Construire le message
            message = self._build_message(course_name, course_url, changes)
            
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
    
    def _build_message(self, course_name: str, course_url: str, changes: list) -> str:
        """Construire le message de notification"""
        message = f"🔔 <b>Mise à jour détectée</b>\n\n"
        message += f"📚 <b>Cours:</b> {course_name}\n"
        message += f"🔗 <b>Lien:</b> <a href='{course_url}'>Accéder au cours</a>\n\n"
        
        message += f"📋 <b>Changements détectés ({len(changes)}):</b>\n\n"
        
        for i, change in enumerate(changes, 1):
            message += f"{i}. <b>{change['message']}</b>\n"
            
            if 'details' in change:
                message += f"   📝 {change['details']}\n"
            
            # Ajouter des emojis selon le type de changement
            if change['type'] == 'section_added':
                message += "   ➕ Nouvelle section\n"
            elif change['type'] == 'section_removed':
                message += "   ➖ Section supprimée\n"
            elif change['type'] == 'activity_added':
                message += "   ➕ Nouvelle activité\n"
            elif change['type'] == 'activity_removed':
                message += "   ➖ Activité supprimée\n"
            elif change['type'] == 'resource_added':
                message += "   ➕ Nouvelle ressource\n"
            elif change['type'] == 'resource_removed':
                message += "   ➖ Ressource supprimée\n"
            elif change['type'] == 'file_added':
                message += "   📁 Nouveau fichier\n"
            elif change['type'] == 'file_removed':
                message += "   🗑️ Fichier supprimé\n"
            elif change['type'] == 'activity_description_changed':
                message += "   ✏️ Description modifiée\n"
            
            message += "\n"
        
        message += f"⏰ <i>Détecté le {self._get_current_time()}</i>"
        
        return message
    
    def _get_current_time(self) -> str:
        """Obtenir l'heure actuelle formatée"""
        from datetime import datetime
        return datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
    
    async def send_startup_message(self):
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
            message += "🔔 Vous recevrez une notification dès qu'un changement sera détecté !"
            
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