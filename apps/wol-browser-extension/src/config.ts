/**
 * Hard configuration. The base URL is a literal so eslint can statically
 * verify no other URL is reachable from a fetch() call site.
 */
export const API_BASE = "http://localhost:8765" as const;
export const HEALTH_TIMEOUT_MS = 2_000;
export const REQUEST_TIMEOUT_MS = 15_000;
