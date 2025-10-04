import crypto from "node:crypto";

export function sha256(input: string): string {
  return crypto.createHash("sha256").update(input).digest("hex");
}

export function normalizeUrl(href: string): string {
  try {
    const url = new URL(href, "https://elearning.univ-bejaia.dz");
    // Drop volatile params
    const volatile = new Set(["forcedownload", "forceview", "time", "v", "t", "_" , "sesskey", "redirect"]);
    for (const key of Array.from(url.searchParams.keys())) {
      if (volatile.has(key)) url.searchParams.delete(key);
    }
    url.hash = "";
    return url.toString();
  } catch {
    return href;
  }
}
