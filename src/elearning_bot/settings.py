import os
import json
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    elearning_username: str
    elearning_password: str
    telegram_bot_token: str
    telegram_chat_id: str
    firebase_project_id: str
    firebase_client_email: str
    firebase_private_key: str
    spaces_json: str
    check_interval_minutes: int
    request_timeout_seconds: int
    log_level: str
    notify_on_first_snapshot: bool


def _get_bool(env_name: str, default: str = "false") -> bool:
    return os.getenv(env_name, default).strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        elearning_username=os.getenv("ELEARNING_USERNAME", ""),
        elearning_password=os.getenv("ELEARNING_PASSWORD", ""),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        firebase_project_id=os.getenv("FIREBASE_PROJECT_ID", ""),
        firebase_client_email=os.getenv("FIREBASE_CLIENT_EMAIL", ""),
        firebase_private_key=os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
        spaces_json=os.getenv("SPACES_JSON", "./config/spaces.json"),
        check_interval_minutes=int(os.getenv("CHECK_INTERVAL_MINUTES", "15")),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        notify_on_first_snapshot=_get_bool("NOTIFY_ON_FIRST_SNAPSHOT", "false"),
    )


def load_spaces(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("spaces", [])
