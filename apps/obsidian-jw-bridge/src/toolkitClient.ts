// Thin REST client around the jw-agent-toolkit REST API (FastAPI).
//
// All endpoints come from packages/jw-mcp/src/jw_mcp/rest_api.py.
// We use `requestUrl` to keep cross-origin and Node-on-mobile compatibility.

import { requestUrl, RequestUrlParam } from "obsidian";

export interface LinkifySettings {
  language: string;
  wtlocale?: string;
  length: "short" | "medium" | "long";
}

export interface VerseSettings extends LinkifySettings {
  template: "plain" | "link" | "blockquote" | "callout" | "callout-collapsed";
  publication: string;
  includeVerseText: boolean;
}

export interface ExportSettings extends LinkifySettings {
  template: "plain" | "link" | "blockquote" | "callout" | "callout-collapsed";
}

export interface LinkifyResponse {
  text: string;
  converted: number;
  skipped_already_linked: number;
}

export interface ConvertLinksResponse {
  text: string;
  bible_converted: number;
  publication_converted: number;
  untouched: number;
  total_converted: number;
}

export interface VerseMarkdownResponse {
  markdown?: string;
  reference?: string;
  language?: string;
  source_url?: string;
  error?: string;
}

export interface IndexVaultResponse {
  vault_root: string;
  indexed: number;
  updated: number;
  deleted: number;
  unchanged: number;
  skipped: number;
  chunks_added: number;
  chunks_removed: number;
}

export interface ExportBackupResponse {
  backup_path: string;
  vault_dir: string;
  files_written: number;
  files_skipped: number;
}

export class JwToolkitClient {
  constructor(private getApiBase: () => string) {}

  private async post<T>(path: string, body: object): Promise<T> {
    const base = this.normalizeBase();
    const param: RequestUrlParam = {
      url: `${base}${path}`,
      method: "POST",
      contentType: "application/json",
      body: JSON.stringify(body),
      throw: false,
    };
    const res = await requestUrl(param);
    if (res.status < 200 || res.status >= 300) {
      throw new Error(`HTTP ${res.status}: ${res.text}`);
    }
    return res.json as T;
  }

  private async get<T>(path: string): Promise<T> {
    const res = await requestUrl({
      url: `${this.normalizeBase()}${path}`,
      method: "GET",
      throw: false,
    });
    if (res.status < 200 || res.status >= 300) {
      throw new Error(`HTTP ${res.status}: ${res.text}`);
    }
    return res.json as T;
  }

  private normalizeBase(): string {
    return this.getApiBase().replace(/\/$/, "");
  }

  async health(): Promise<boolean> {
    try {
      const res = await this.get<{ status: string }>("/healthz");
      return res.status === "ok";
    } catch {
      return false;
    }
  }

  linkify(text: string, settings: LinkifySettings): Promise<LinkifyResponse> {
    return this.post<LinkifyResponse>("/api/v1/linkify", {
      text,
      language: settings.language,
      length: settings.length,
      wtlocale: settings.wtlocale ?? "",
    });
  }

  convertLinks(text: string, kind: "bible" | "publication" | "all" = "all"): Promise<ConvertLinksResponse> {
    return this.post<ConvertLinksResponse>("/api/v1/convert_links", { text, kind, wtlocale: "" });
  }

  getVerseMarkdown(reference: string, settings: VerseSettings): Promise<VerseMarkdownResponse> {
    return this.post<VerseMarkdownResponse>("/api/v1/verse_markdown", {
      reference,
      language: settings.language,
      template: settings.template,
      length: settings.length,
      publication: settings.publication,
      include_text: settings.includeVerseText,
    });
  }

  indexVault(vaultRoot: string): Promise<IndexVaultResponse> {
    return this.post<IndexVaultResponse>("/api/v1/vault/index", { vault_root: vaultRoot });
  }

  exportBackup(
    backupPath: string,
    vaultDir: string,
    settings: ExportSettings,
    subdir: string
  ): Promise<ExportBackupResponse> {
    return this.post<ExportBackupResponse>("/api/v1/vault/export", {
      backup_path: backupPath,
      vault_dir: vaultDir,
      template: settings.template,
      length: settings.length,
      language: settings.language,
      subdir,
      overwrite: false,
    });
  }
}
