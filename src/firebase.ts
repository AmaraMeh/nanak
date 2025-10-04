import admin from "firebase-admin";
import fs from "node:fs";
import { appConfig } from "./config.js";

function initializeFirebaseAdmin(): admin.app.App | null {
  if (admin.apps.length) {
    return admin.app();
  }

  let credential: admin.credential.Credential | undefined;

  if (appConfig.FIREBASE_SERVICE_ACCOUNT_JSON) {
    const json = JSON.parse(appConfig.FIREBASE_SERVICE_ACCOUNT_JSON);
    credential = admin.credential.cert(json);
  } else if (appConfig.GOOGLE_APPLICATION_CREDENTIALS) {
    const p = appConfig.GOOGLE_APPLICATION_CREDENTIALS;
    if (!fs.existsSync(p)) {
      throw new Error(`GOOGLE_APPLICATION_CREDENTIALS not found at: ${p}`);
    }
    credential = admin.credential.cert(p);
  } else {
    // No Firebase configured; allow fallback to filesystem
    return null;
  }

  return admin.initializeApp({
    credential,
  });
}

export const firebaseApp = initializeFirebaseAdmin();
export const firestore: FirebaseFirestore.Firestore | null = firebaseApp
  ? admin.firestore(firebaseApp)
  : null;
