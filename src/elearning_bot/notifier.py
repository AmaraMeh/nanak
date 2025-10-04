import logging
from typing import List

from telegram import Bot

from .models import Change

LOGGER = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    async def send_changes(self, changes: List[Change]) -> None:
        for change in changes:
            prefix = {
                "added": "🆕 Ajout",
                "modified": "✏️ Modification",
                "removed": "🗑️ Suppression",
            }.get(change.change_type, "🔔 Mise à jour")
            title = change.title or change.item_id
            link = change.url or ""
            space_url = (change.extra or {}).get("space_url", "")
            text = (
                f"{prefix} dans {change.space_name}\n"
                f"• Titre: {title}\n"
                f"• Lien espace: {space_url}\n"
                f"• Lien item: {link}"
            )
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=text)
            except Exception as e:
                LOGGER.error("Failed to send message: %s", e)
