import { chromium, Browser, Page } from "playwright";
import fs from "node:fs";
import { appConfig } from "./config.js";
import { Course, CourseSnapshot, ScrapedItem } from "./types.js";
import { normalizeUrl, sha256 } from "./utils.js";

async function loginIfNeeded(page: Page): Promise<void> {
  await page.goto(`${appConfig.ELEARNING_BASE_URL}/my/`, { waitUntil: "domcontentloaded" });

  const loggedIn = await page.locator('#user-menu-toggle, a[href*="logout"], a[aria-label*="Logout" i]').first().isVisible().catch(() => false);
  if (loggedIn) return;

  await page.goto(`${appConfig.ELEARNING_BASE_URL}/login/index.php`, { waitUntil: "domcontentloaded" });
  await page.fill('#username', appConfig.ELEARNING_USERNAME);
  await page.fill('#password', appConfig.ELEARNING_PASSWORD);

  const hasLoginBtn = await page.locator('#loginbtn').count();
  if (hasLoginBtn) {
    await page.click('#loginbtn');
  } else {
    await page.click('button[type="submit"]');
  }

  await page.waitForLoadState('domcontentloaded');

  const ok = await page.locator('#user-menu-toggle, a[href*="logout"]').first().isVisible().catch(() => false);
  if (!ok) {
    throw new Error('Login failed. Check credentials or captcha.');
  }
}

function extractCourseId(url: string): string {
  try {
    const u = new URL(url);
    const id = u.searchParams.get('id');
    if (!id) return url;
    return id;
  } catch {
    return url;
  }
}

async function scrapeCourse(page: Page, course: Course): Promise<CourseSnapshot> {
  await page.goto(course.url, { waitUntil: 'domcontentloaded' });

  const regionSelector = '#region-main, #page-content';
  await page.waitForSelector(regionSelector, { timeout: 20000 }).catch(() => {});

  const items = await page.evaluate(() => {
    const results: { type: string; title: string; href?: string; context?: string }[] = [];

    function addItem(item: { type: string; title: string; href?: string; context?: string }) {
      const title = (item.title || '').trim();
      if (!title) return;
      results.push(item);
    }

    const region = document.querySelector('#region-main') || document.querySelector('#page-content') || document.body;

    // Headings
    region.querySelectorAll('h1, h2, h3').forEach((el) => {
      addItem({ type: 'heading', title: (el as HTMLElement).innerText });
    });

    // Activity/file tiles
    region.querySelectorAll('li.activity, div.activity, .activityinstance, .activityname').forEach((el) => {
      const link = el.querySelector('a');
      const title = link?.textContent || (el as HTMLElement).innerText;
      const href = link?.getAttribute('href') || undefined;
      addItem({ type: href ? 'file' : 'text', title: title || '', href: href });
    });

    // All links (as fallback)
    region.querySelectorAll('a[href]').forEach((a) => {
      const href = (a as HTMLAnchorElement).href;
      const title = (a as HTMLElement).innerText || a.getAttribute('title') || href;
      addItem({ type: 'link', title: title, href });
    });

    return results;
  });

  // Normalize and de-duplicate
  const normalized: ScrapedItem[] = [];
  const seen = new Set<string>();
  for (const raw of items) {
    const href = raw.href ? normalizeUrl(raw.href) : undefined;
    const key = href ? `href:${href}` : `title:${raw.title.toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    normalized.push({ type: raw.type as any, title: raw.title.trim(), href, context: raw.context });
  }

  const contentHash = sha256(JSON.stringify(normalized));
  const snapshot: CourseSnapshot = {
    courseId: course.id,
    courseName: course.name,
    url: course.url,
    fetchedAt: new Date().toISOString(),
    items: normalized,
    contentHash,
  };
  return snapshot;
}

export class ElearningScraper {
  private browser: Browser | null = null;

  async init(): Promise<void> {
    const headless = appConfig.PLAYWRIGHT_HEADLESS;
    this.browser = await chromium.launch({ headless });
  }

  async close(): Promise<void> {
    if (this.browser) {
      await this.browser.close();
      this.browser = null;
    }
  }

  async fetchSnapshots(courses: Course[]): Promise<CourseSnapshot[]> {
    if (!this.browser) await this.init();
    if (!this.browser) throw new Error('Browser not initialized');
    const context = await this.browser.newContext({
      storageState: fs.existsSync(appConfig.STORAGE_STATE_PATH) ? appConfig.STORAGE_STATE_PATH : undefined,
    });
    const page = await context.newPage();
    await loginIfNeeded(page);
    await context.storageState({ path: appConfig.STORAGE_STATE_PATH });

    const snapshots: CourseSnapshot[] = [];

    for (const course of courses) {
      try {
        const snap = await scrapeCourse(page, course);
        snapshots.push(snap);
      } catch (err) {
        console.error(`[SCRAPE] Failed for ${course.name}:`, (err as Error).message);
      }
    }

    await page.close();
    await context.close();

    return snapshots;
  }
}

export function toCourse(url: string, name: string): Course {
  return { id: extractCourseId(url), url, name };
}
