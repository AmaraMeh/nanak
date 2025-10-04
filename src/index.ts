import cron from "node-cron";
import { runMonitorOnce } from "./monitor.js";
import { appConfig } from "./config.js";

async function main(): Promise<void> {
  console.log(`[BOT] Elearning monitor starting. Schedule: ${appConfig.CRON_SCHEDULE}`);

  // Run immediately at startup
  try {
    await runMonitorOnce();
    console.log("[BOT] Initial run completed.");
  } catch (err) {
    console.error("[BOT] Initial run error:", (err as Error).message);
  }

  // Schedule
  cron.schedule(appConfig.CRON_SCHEDULE, async () => {
    console.log(`[BOT] Scheduled run started at ${new Date().toISOString()}`);
    try {
      await runMonitorOnce();
      console.log("[BOT] Scheduled run completed.");
    } catch (err) {
      console.error("[BOT] Scheduled run error:", (err as Error).message);
    }
  });
}

main().catch((e) => {
  console.error("[BOT] Fatal:", e);
  process.exit(1);
});
