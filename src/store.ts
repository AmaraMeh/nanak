import { firestore } from "./firebase.js";
import { appConfig } from "./config.js";
import { CourseSnapshot } from "./types.js";

const coursesCollection = () => firestore.collection(appConfig.FIRESTORE_COLLECTION);
const settingsCollection = () => firestore.collection(appConfig.FIRESTORE_SETTINGS_COLLECTION);

export async function getPreviousSnapshot(courseId: string): Promise<CourseSnapshot | null> {
  const doc = await coursesCollection().doc(courseId).get();
  if (!doc.exists) return null;
  return doc.data() as CourseSnapshot;
}

export async function saveSnapshot(snapshot: CourseSnapshot): Promise<void> {
  await coursesCollection().doc(snapshot.courseId).set(snapshot, { merge: true });
}

export async function getStoredTelegramChatId(): Promise<string | null> {
  const doc = await settingsCollection().doc("telegram").get();
  if (!doc.exists) return null;
  const data = doc.data();
  return (data?.chatId as string) || null;
}

export async function saveTelegramChatId(chatId: string): Promise<void> {
  await settingsCollection().doc("telegram").set({ chatId }, { merge: true });
}
