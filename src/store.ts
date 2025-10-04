import fs from "node:fs";
import path from "node:path";
import { firestore } from "./firebase.js";
import { appConfig } from "./config.js";
import { CourseSnapshot } from "./types.js";

const dataDir = path.resolve("data");
const fsSnapshotsPath = path.join(dataDir, "snapshots.json");
const fsSettingsPath = path.join(dataDir, "settings.json");

function ensureDataDir() {
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
}

function readJson<T>(p: string, fallback: T): T {
  try {
    const raw = fs.readFileSync(p, "utf8");
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson<T>(p: string, data: T): void {
  ensureDataDir();
  fs.writeFileSync(p, JSON.stringify(data, null, 2), "utf8");
}

const usingFirestore = !!firestore;

const coursesCollection = () => firestore!.collection(appConfig.FIRESTORE_COLLECTION);
const settingsCollection = () => firestore!.collection(appConfig.FIRESTORE_SETTINGS_COLLECTION);

export async function getPreviousSnapshot(courseId: string): Promise<CourseSnapshot | null> {
  if (usingFirestore) {
    const doc = await coursesCollection().doc(courseId).get();
    if (!doc.exists) return null;
    return doc.data() as CourseSnapshot;
  }

  const all = readJson<Record<string, CourseSnapshot>>(fsSnapshotsPath, {});
  return all[courseId] || null;
}

export async function saveSnapshot(snapshot: CourseSnapshot): Promise<void> {
  if (usingFirestore) {
    await coursesCollection().doc(snapshot.courseId).set(snapshot, { merge: true });
    return;
  }
  const all = readJson<Record<string, CourseSnapshot>>(fsSnapshotsPath, {});
  all[snapshot.courseId] = snapshot;
  writeJson(fsSnapshotsPath, all);
}

export async function getStoredTelegramChatId(): Promise<string | null> {
  if (usingFirestore) {
    const doc = await settingsCollection().doc("telegram").get();
    if (!doc.exists) return null;
    const data = doc.data();
    return (data?.chatId as string) || null;
  }
  const settings = readJson<Record<string, any>>(fsSettingsPath, {});
  return settings.telegram?.chatId ?? null;
}

export async function saveTelegramChatId(chatId: string): Promise<void> {
  if (usingFirestore) {
    await settingsCollection().doc("telegram").set({ chatId }, { merge: true });
    return;
  }
  const settings = readJson<Record<string, any>>(fsSettingsPath, {});
  settings.telegram = { chatId };
  writeJson(fsSettingsPath, settings);
}
