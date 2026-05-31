import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderPopup, savePopupSettings } from "../../src/popup/popup";

interface FakeStorageLocal {
  _store: Record<string, unknown>;
  get: (keys: string[]) => Promise<Record<string, unknown>>;
  set: (obj: Record<string, unknown>) => Promise<void>;
}

interface GlobalWithChrome {
  chrome?: {
    storage: { local: FakeStorageLocal };
    runtime: { sendMessage: (msg: unknown) => Promise<{ ok: boolean }> };
  };
}

describe("popup", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="root"></div>`;
    const store: Record<string, unknown> = {};
    const fake: FakeStorageLocal = {
      _store: store,
      get: vi.fn((keys: string[]) => {
        const out: Record<string, unknown> = {};
        for (const k of keys) out[k] = store[k];
        return Promise.resolve(out);
      }),
      set: vi.fn((obj: Record<string, unknown>) => {
        Object.assign(store, obj);
        return Promise.resolve();
      }),
    };
    (globalThis as unknown as GlobalWithChrome).chrome = {
      storage: { local: fake },
      runtime: { sendMessage: vi.fn(() => Promise.resolve({ ok: true })) },
    };
  });

  it("renders inputs and labels", async () => {
    await renderPopup(document.getElementById("root")!, "en");
    expect(document.querySelector("#vault_path")).not.toBeNull();
    expect(document.querySelector("#language")).not.toBeNull();
    expect(document.querySelector("#save")).not.toBeNull();
    expect(document.querySelector("h1")?.textContent).toMatch(/JW Toolkit/);
  });

  it("savePopupSettings writes to chrome.storage.local", async () => {
    await savePopupSettings({ vault_path: "/x/vault", language: "es" });
    const storage = (globalThis as unknown as GlobalWithChrome).chrome!.storage
      .local;
    expect(storage.set).toHaveBeenCalledWith({
      vault_path: "/x/vault",
      language: "es",
    });
  });
});
