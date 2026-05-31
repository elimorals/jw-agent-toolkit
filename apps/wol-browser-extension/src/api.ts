import { API_BASE, HEALTH_TIMEOUT_MS, REQUEST_TIMEOUT_MS } from "./config";
import type {
  CrossRefRequest,
  CrossRefResponse,
  VaultAppendRequest,
  VaultAppendResponse,
  VerseMarkdownRequest,
  VerseMarkdownResponse,
} from "./types";

export class ApiError extends Error {
  public readonly status: number;
  public readonly bodyExcerpt: string;

  constructor(status: number, bodyExcerpt: string) {
    super(`API ${status}: ${bodyExcerpt.slice(0, 200)}`);
    this.status = status;
    this.bodyExcerpt = bodyExcerpt;
  }
}

/**
 * Thin wrapper around fetch. Refuses to call any URL not starting with
 * API_BASE — defense-in-depth on top of manifest host_permissions.
 */
export class JwApiClient {
  private readonly base: string;

  constructor(base: string = API_BASE) {
    if (base !== API_BASE) {
      throw new Error(
        `JwApiClient refuses non-default base ${base} (only ${API_BASE} allowed)`,
      );
    }
    this.base = base;
  }

  private assertLocal(url: string): void {
    if (!url.startsWith(`${API_BASE}/`)) {
      throw new Error(`refuses non-localhost URL: ${url}`);
    }
  }

  private async request<T>(
    url: string,
    method: "GET" | "POST",
    body?: unknown,
    timeoutMs: number = REQUEST_TIMEOUT_MS,
  ): Promise<T> {
    this.assertLocal(url);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const init: RequestInit = {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        signal: ctrl.signal,
      };
      if (body !== undefined) {
        init.body = JSON.stringify(body);
      }
      const r = await fetch(url, init);
      if (!r.ok) {
        const text = await r.text();
        throw new ApiError(r.status, text);
      }
      return (await r.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }

  async health(): Promise<{ status: string }> {
    return this.request<{ status: string }>(
      `${this.base}/healthz`,
      "GET",
      undefined,
      HEALTH_TIMEOUT_MS,
    );
  }

  async healthOrNull(): Promise<{ status: string } | null> {
    try {
      return await this.health();
    } catch {
      return null;
    }
  }

  async verseMarkdown(
    req: VerseMarkdownRequest,
  ): Promise<VerseMarkdownResponse> {
    return this.request<VerseMarkdownResponse>(
      `${this.base}/api/v1/verse_markdown`,
      "POST",
      req,
    );
  }

  async crossRefs(req: CrossRefRequest): Promise<CrossRefResponse> {
    return this.request<CrossRefResponse>(
      `${this.base}/api/v1/cross_references`,
      "POST",
      req,
    );
  }

  async vaultAppend(req: VaultAppendRequest): Promise<VaultAppendResponse> {
    return this.request<VaultAppendResponse>(
      `${this.base}/api/v1/vault/append`,
      "POST",
      req,
    );
  }
}
