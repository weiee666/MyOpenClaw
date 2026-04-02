const MAX_DNS_LABEL_LENGTH = 63;

export function normalizeUserId(input) {
  if (!input || typeof input !== "string") {
    throw new Error("userId is required");
  }
  const trimmed = input.trim().toLowerCase();
  if (!trimmed) {
    throw new Error("userId is required");
  }
  const normalized = trimmed
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (!normalized) {
    throw new Error("userId must include letters or numbers");
  }
  return normalized.slice(0, MAX_DNS_LABEL_LENGTH);
}

export function ensureToken(label, value) {
  if (!value || typeof value !== "string" || !value.trim()) {
    throw new Error(`${label} is required`);
  }
  return value.trim();
}

export function buildName(prefix, suffix) {
  const cleanSuffix = suffix.replace(/^-+/, "");
  const maxSuffix = Math.max(1, MAX_DNS_LABEL_LENGTH - prefix.length);
  return `${prefix}${cleanSuffix.slice(0, maxSuffix)}`;
}
