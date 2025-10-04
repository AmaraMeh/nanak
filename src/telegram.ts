import axios from "axios";
import { appConfig } from "./config.js";
import { getStoredTelegramChatId, saveTelegramChatId } from "./store.js";

const apiBase = `https://api.telegram.org/bot${appConfig.TELEGRAM_BOT_TOKEN}`;

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export async function ensureTelegramChatId(): Promise<string> {
  if (appConfig.TELEGRAM_CHAT_ID) return appConfig.TELEGRAM_CHAT_ID;

  const stored = await getStoredTelegramChatId();
  if (stored) return stored;

  // Attempt to auto-capture chat ID from recent updates
  try {
    const { data } = await axios.get(`${apiBase}/getUpdates`, { timeout: 15000 });
    const updates = (data?.result as any[]) || [];
    const lastPrivate = updates
      .map((u) => u.message?.chat)
      .filter((c) => c && c.type === "private")
      .pop();

    if (lastPrivate?.id) {
      const chatId = String(lastPrivate.id);
      await saveTelegramChatId(chatId);
      return chatId;
    }
  } catch {
    // ignore
  }

  throw new Error(
    "TELEGRAM_CHAT_ID not set and could not auto-detect. Send /start to your bot then rerun."
  );
}

export async function sendTelegramMessage(chatId: string, html: string): Promise<void> {
  await axios.post(
    `${apiBase}/sendMessage`,
    {
      chat_id: chatId,
      text: html,
      parse_mode: "HTML",
      disable_web_page_preview: true,
    },
    { timeout: 20000 }
  );
}

export function buildChangeMessage(courseName: string, courseUrl: string, reportLines: string[]): string {
  const lines = [
    `<b>${escapeHtml(courseName)}</b>`,
    `<a href=\"${courseUrl}\">Ouvrir l'espace</a>`,
    "",
    ...reportLines.map((l) => escapeHtml(l)),
  ];
  return lines.join("\n");
}
