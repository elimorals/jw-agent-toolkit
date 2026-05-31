import { describe, expect, it } from "vitest";

import manifest from "../../manifest.json";

describe("manifest v3 contract", () => {
  it("declares manifest_version 3", () => {
    expect(manifest.manifest_version).toBe(3);
  });

  it("only allows localhost:8765 in host_permissions", () => {
    expect(manifest.host_permissions).toEqual(["http://localhost:8765/*"]);
  });

  it("content_scripts target wol.jw.org only", () => {
    expect(manifest.content_scripts).toHaveLength(1);
    expect(manifest.content_scripts[0]!.matches).toEqual(["https://wol.jw.org/*"]);
  });

  it("permissions list is minimal (storage only)", () => {
    expect(manifest.permissions).toEqual(["storage"]);
    expect(manifest.permissions).not.toContain("tabs");
    expect(manifest.permissions).not.toContain("webRequest");
    expect(manifest.permissions).not.toContain("cookies");
  });

  it("declares a Firefox gecko id for self-distribution AMO", () => {
    expect(manifest.browser_specific_settings?.gecko?.id).toBe(
      "jw-agent-toolkit@cipre.dev",
    );
  });
});
