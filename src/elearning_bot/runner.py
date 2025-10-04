import asyncio
import logging
from typing import Dict, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .settings import load_settings, load_spaces
from .logger import configure_logging
from .scraper import MoodleScraper
from .storage import FirestoreStore
from .diff import diff_snapshots
from .models import Change
from .notifier import TelegramNotifier


LOGGER = logging.getLogger(__name__)
BASE_URL = "https://elearning.univ-bejaia.dz"


async def check_once(scraper: MoodleScraper, store: FirestoreStore, notifier: TelegramNotifier, spaces: List[dict], notify_on_first_snapshot: bool) -> None:
    all_changes: List[Change] = []

    for space in spaces:
        name = space["name"]
        url = space["url"]
        space_key = f"{name}"
        try:
            _, items = scraper.fetch_course(url)
            # annotate items with space url for notifier convenience
            for _id, _it in items.items():
                _it.setdefault("extra", {})
                _it["extra"]= {**_it.get("extra", {}), "space_url": url}
        except Exception as e:
            LOGGER.error("Failed to fetch %s: %s", name, e)
            continue

        old_items = store.get_snapshot(space_key)
        if old_items is None:
            store.save_snapshot(space_key, items)
            LOGGER.info("Initialized snapshot for %s (%d items)", name, len(items))
            if notify_on_first_snapshot:
                # synthesize 'added' changes for first time if desired
                for item_id, item in items.items():
                    all_changes.append(
                        Change(
                            space_name=name,
                            change_type="added",
                            item_id=item_id,
                            title=item.get("title", item_id),
                            url=item.get("url"),
                            extra={"space_url": url},
                        )
                    )
            continue

        changes = diff_snapshots(name, old_items, items)
        if changes:
            store.save_snapshot(space_key, items)
            # Attach space url into change.extra when missing
            for ch in changes:
                ex = ch.extra or {}
                if "space_url" not in ex:
                    ex["space_url"] = url
                ch.extra = ex
            all_changes.extend(changes)

    if all_changes:
        await notifier.send_changes(all_changes)
        LOGGER.info("Sent %d changes", len(all_changes))
    else:
        LOGGER.info("No changes detected")


async def main_async() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    scraper = MoodleScraper(BASE_URL, settings.elearning_username, settings.elearning_password, timeout=settings.request_timeout_seconds)

    store = FirestoreStore(
        project_id=settings.firebase_project_id,
        client_email=settings.firebase_client_email,
        private_key=settings.firebase_private_key,
    )
    store.initialize()

    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)

    spaces = load_spaces(settings.spaces_json)

    # Run immediately on start
    await check_once(scraper, store, notifier, spaces, settings.notify_on_first_snapshot)

    # Schedule every N minutes
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_once, "interval", minutes=settings.check_interval_minutes, args=[scraper, store, notifier, spaces, settings.notify_on_first_snapshot])
    scheduler.start()

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        pass


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
