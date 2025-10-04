import pLimit from "p-limit";
import { COURSES } from "./courses.js";
import { ElearningScraper } from "./scraper.js";
import { diffSnapshots } from "./diff.js";
import { getPreviousSnapshot, saveSnapshot } from "./store.js";
import { buildChangeMessage, ensureTelegramChatId, sendTelegramMessage } from "./telegram.js";
import { appConfig } from "./config.js";

export async function runMonitorOnce(): Promise<void> {
  const scraper = new ElearningScraper();
  try {
    await scraper.init();
    const snapshots = await scraper.fetchSnapshots(COURSES);

    const chatId = await ensureTelegramChatId();

    const limiter = pLimit(appConfig.SCRAPE_CONCURRENCY);

    await Promise.all(
      snapshots.map((snap) => limiter(async () => {
        const prev = await getPreviousSnapshot(snap.courseId);
        if (!prev) {
          // First-time snapshot: store baseline without notifying
          await saveSnapshot(snap);
          return;
        }

        if (prev.contentHash === snap.contentHash) {
          // No change
          return;
        }

        const changes = diffSnapshots(prev, snap);
        if (changes.length > 0) {
          const lines: string[] = changes.slice(0, 50).map((c) => {
            const title = c.item.title;
            const href = c.item.href ? ` (lien)` : "";
            if (c.type === "added") return `➕ Ajouté: ${title}${href}`;
            if (c.type === "removed") return `➖ Supprimé: ${title}${href}`;
            return `✏️ Modifié: ${title}${href}`;
          });
          const message = buildChangeMessage(snap.courseName, snap.url, lines);
          await sendTelegramMessage(chatId, message);
        }

        await saveSnapshot(snap);
      }))
    );
  } finally {
    await scraper.close();
  }
}
