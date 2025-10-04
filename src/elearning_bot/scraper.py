import logging
import re
import time
import hashlib
from typing import Dict, Tuple

import cloudscraper
from bs4 import BeautifulSoup
from user_agent import generate_user_agent

LOGGER = logging.getLogger(__name__)


class MoodleScraper:
    def __init__(self, base_url: str, username: str, password: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        self.session.headers.update({
            "User-Agent": generate_user_agent(),
            "Referer": self.base_url,
        })
        self.logged_in = False

    def login(self) -> None:
        login_page_url = f"{self.base_url}/login/index.php"
        LOGGER.info("Fetching login page to get token")
        resp = self.session.get(login_page_url, timeout=self.timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html5lib")
        logintoken = None
        token_el = soup.find("input", {"name": "logintoken"})
        if token_el:
            logintoken = token_el.get("value")

        payload = {
            "username": self.username,
            "password": self.password,
        }
        if logintoken:
            payload["logintoken"] = logintoken

        LOGGER.info("Posting credentials to login")
        post = self.session.post(login_page_url, data=payload, timeout=self.timeout)
        post.raise_for_status()

        if "logout" in post.text.lower() or "/logout.php" in post.text:
            self.logged_in = True
            LOGGER.info("Authenticated successfully")
        else:
            # Moodle sometimes redirects; check homepage after login
            home = self.session.get(f"{self.base_url}/", timeout=self.timeout)
            if "logout" in home.text.lower() or "/logout.php" in home.text:
                self.logged_in = True
                LOGGER.info("Authenticated successfully after redirect")
            else:
                raise RuntimeError("Login failed")

    def fetch_course(self, course_url: str) -> Tuple[str, Dict[str, Dict]]:
        if not self.logged_in:
            self.login()

        LOGGER.info("Fetching course page: %s", course_url)
        r = self.session.get(course_url, timeout=self.timeout)
        r.raise_for_status()

        html = r.text
        soup = BeautifulSoup(html, "html5lib")

        # Extract a normalized set of items: sections, activities, resources, announcements.
        items: Dict[str, Dict] = {}

        # Use a few generic selectors that work on Moodle course pages
        # Each activity/resource often has id like module-XXXX with .activity
        for mod in soup.select("li.activity"):
            mod_id = mod.get("id") or ""
            if not mod_id:
                continue
            title_link = mod.select_one(".activityinstance a")
            title = title_link.get_text(strip=True) if title_link else mod.get_text(strip=True)
            url = title_link.get("href") if title_link else None
            # Stable hash across runs
            hash_input = f"{title}|{url or ''}".encode("utf-8")
            content_hash = hashlib.sha256(hash_input).hexdigest()
            items[mod_id] = {"title": title, "url": url, "hash": content_hash}

        # Also catch files and links that might not be in activity list
        for a in soup.select("a"):
            href = a.get("href")
            text = a.get_text(strip=True)
            if not href or not text:
                continue
            if "mod/resource" in href or "pluginfile.php" in href or "mod/forum" in href:
                anchor_id = "a-" + hashlib.sha1(href.encode("utf-8")).hexdigest()
                items.setdefault(
                    anchor_id,
                    {
                        "title": text,
                        "url": href,
                        "hash": hashlib.sha256(f"{text}|{href}".encode("utf-8")).hexdigest(),
                    },
                )

        return html, items
