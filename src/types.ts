export interface Course {
  id: string; // e.g. "19984"
  name: string;
  url: string;
}

export interface ScrapedItem {
  type: "link" | "heading" | "file" | "text";
  title: string;
  href?: string;
  context?: string; // e.g. section heading
}

export interface CourseSnapshot {
  courseId: string;
  courseName: string;
  url: string;
  fetchedAt: string; // ISO
  items: ScrapedItem[];
  contentHash: string; // sha256 of normalized items
}

export interface ChangeDetail {
  type: "added" | "removed" | "modified";
  item: ScrapedItem;
  previous?: ScrapedItem;
}
