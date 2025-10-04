import { config as loadDotenv } from "dotenv";
import { z } from "zod";
import fs from "node:fs";
import path from "node:path";

loadDotenv();

const schema = z.object({
  ELEARNING_BASE_URL: z.string().url().default("https://elearning.univ-bejaia.dz"),
  ELEARNING_USERNAME: z.string().min(3),
  ELEARNING_PASSWORD: z.string().min(3),
  TELEGRAM_BOT_TOKEN: z.string().min(10),
  TELEGRAM_CHAT_ID: z.string().optional(),
  CRON_SCHEDULE: z.string().default("*/15 * * * *"),
  PLAYWRIGHT_HEADLESS: z
    .string()
    .default("true")
    .transform((v) => v.toLowerCase() === "true"),
  SCRAPE_CONCURRENCY: z
    .string()
    .default("3")
    .transform((v) => Math.max(1, parseInt(v, 10) || 3)),
  STORAGE_STATE_PATH: z.string().default("./data/storage-state.json"),
  FIRESTORE_COLLECTION: z.string().default("elearning_courses"),
  FIRESTORE_SETTINGS_COLLECTION: z.string().default("settings"),
  GOOGLE_APPLICATION_CREDENTIALS: z.string().optional(),
  FIREBASE_SERVICE_ACCOUNT_JSON: z.string().optional(),
});

const parsed = schema.safeParse(process.env);
if (!parsed.success) {
  // Show concise errors without secrets
  const errs = parsed.error.errors.map((e) => `${e.path.join(".")}: ${e.message}`).join(", ");
  throw new Error(`Invalid configuration: ${errs}`);
}

export const appConfig = parsed.data;

// Ensure data directory exists for storage state
const storageDir = path.dirname(appConfig.STORAGE_STATE_PATH);
if (!fs.existsSync(storageDir)) {
  fs.mkdirSync(storageDir, { recursive: true });
}
