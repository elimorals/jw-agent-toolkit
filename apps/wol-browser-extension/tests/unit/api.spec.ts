import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, JwApiClient } from "../../src/api";

describe("JwApiClient", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  it("only ever calls http://localhost:8765", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    const client = new JwApiClient();
    await client.health();
    expect(fetchMock).toHaveBeenCalledOnce();
    const url = fetchMock.mock.calls[0]![0] as string;
    expect(url.startsWith("http://localhost:8765/")).toBe(true);
  });

  it("refuses to construct a request to a non-localhost URL", async () => {
    const client = new JwApiClient();
    // Bracket access bypasses the `private` visibility for this defense check.
    await expect(
      (
        client as unknown as {
          request: (u: string, m: string) => Promise<unknown>;
        }
      ).request("https://wol.jw.org/evil", "GET"),
    ).rejects.toThrow(/non-localhost/);
  });

  it("verse_markdown POSTs reference body and returns markdown", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          markdown: "> Juan 3:16 ...",
          reference: "Juan 3:16",
          language: "es",
          source_url: "https://wol.jw.org/x",
        }),
        { status: 200 },
      ),
    );
    const client = new JwApiClient();
    const out = await client.verseMarkdown({
      reference: "Juan 3:16",
      language: "es",
      template: "callout",
    });
    expect(out.markdown).toContain("Juan 3:16");
    const [, init] = fetchMock.mock.calls[0]!;
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      reference: "Juan 3:16",
      language: "es",
      template: "callout",
    });
  });

  it("throws ApiError on non-2xx", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "bad" }), { status: 400 }),
    );
    const client = new JwApiClient();
    await expect(client.health()).rejects.toBeInstanceOf(ApiError);
  });

  it("returns null on network failure (does not surface URL)", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const client = new JwApiClient();
    const ok = await client.healthOrNull();
    expect(ok).toBe(null);
  });

  it("crossRefs invokes /api/v1/cross_references", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ refs: [{ verse: "John 1:1", url: "x" }] }),
        { status: 200 },
      ),
    );
    const client = new JwApiClient();
    const out = await client.crossRefs({ reference: "John 3:16", language: "en" });
    expect(out.refs).toHaveLength(1);
    expect(fetchMock.mock.calls[0]![0]).toBe(
      "http://localhost:8765/api/v1/cross_references",
    );
  });

  it("vaultAppend invokes /api/v1/vault/append", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true, path: "/v/Verses/x.md" }), {
        status: 200,
      }),
    );
    const client = new JwApiClient();
    const out = await client.vaultAppend({
      reference: "John 3:16",
      vault_path: "/Users/x/vault",
      template: "callout",
      language: "en",
    });
    expect(out.ok).toBe(true);
    expect(fetchMock.mock.calls[0]![0]).toBe(
      "http://localhost:8765/api/v1/vault/append",
    );
  });
});
