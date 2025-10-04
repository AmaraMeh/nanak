import admin from "firebase-admin";
import fs from "node:fs";
import { appConfig } from "./config.js";

function initializeFirebaseAdmin(): admin.app.App {
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
    throw new Error(
      "Firebase Admin requires service account. Set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_JSON"
    );
  }

  return admin.initializeApp({
    credential,
  });
}

export const firebaseApp = initializeFirebaseAdmin();
export const firestore = admin.firestore(firebaseApp);
