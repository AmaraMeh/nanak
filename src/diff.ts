import { CourseSnapshot, ChangeDetail, ScrapedItem } from "./types.js";

function itemKey(item: ScrapedItem): string {
  return item.href ? `href:${item.href}` : `title:${item.title.toLowerCase()}`;
}

export function diffSnapshots(prev: CourseSnapshot, curr: CourseSnapshot): ChangeDetail[] {
  const prevMap = new Map<string, ScrapedItem>(prev.items.map((i) => [itemKey(i), i]));
  const currMap = new Map<string, ScrapedItem>(curr.items.map((i) => [itemKey(i), i]));

  const changes: ChangeDetail[] = [];

  // Added
  for (const [key, item] of currMap.entries()) {
    if (!prevMap.has(key)) {
      changes.push({ type: "added", item });
    }
  }

  // Removed
  for (const [key, item] of prevMap.entries()) {
    if (!currMap.has(key)) {
      changes.push({ type: "removed", item });
    }
  }

  // Modified (same key but different title or context)
  for (const [key, currItem] of currMap.entries()) {
    const prevItem = prevMap.get(key);
    if (!prevItem) continue;
    if (prevItem.title.trim() !== currItem.title.trim() || (prevItem.context || "") !== (currItem.context || "")) {
      changes.push({ type: "modified", item: currItem, previous: prevItem });
    }
  }

  return changes;
}
