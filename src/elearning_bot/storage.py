import logging
from typing import Dict, Optional

import firebase_admin
from firebase_admin import credentials, firestore

LOGGER = logging.getLogger(__name__)


class FirestoreStore:
    def __init__(self, project_id: str, client_email: str, private_key: str) -> None:
        self.project_id = project_id
        self.client_email = client_email
        self.private_key = private_key
        self.app = None
        self.db = None

    def initialize(self) -> None:
        if firebase_admin._apps:
            self.app = firebase_admin.get_app()
        else:
            cred = credentials.Certificate(
                {
                    "type": "service_account",
                    "project_id": self.project_id,
                    "client_email": self.client_email,
                    "private_key": self.private_key,
                    "private_key_id": "dummy",
                    "client_id": "dummy",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            )
            self.app = firebase_admin.initialize_app(cred, {
                "projectId": self.project_id,
            })
        self.db = firestore.client(app=self.app)

    def get_snapshot(self, space_key: str) -> Optional[Dict[str, Dict]]:
        doc = self.db.collection("elearning_snapshots").document(space_key).get()
        if doc.exists:
            data = doc.to_dict() or {}
            return data.get("items", {})
        return None

    def save_snapshot(self, space_key: str, items: Dict[str, Dict]) -> None:
        self.db.collection("elearning_snapshots").document(space_key).set({
            "items": items
        })
