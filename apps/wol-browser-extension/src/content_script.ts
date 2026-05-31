import { JwApiClient } from "./api";
import { injectButtonsForVerses } from "./dom/button_injector";
import {
  showToast,
  showTooltip,
  showTooltipLinks,
  showTooltipText,
} from "./dom/tooltip";
import {
  buildReferenceFromUrl,
  detectVerses,
} from "./dom/verse_detector";
import { createTranslator, detectLanguage } from "./i18n";
import type { Language, VerseTarget } from "./types";

interface RunOpts {
  onExplain?: (t: VerseTarget) => void;
  onCrossRefs?: (t: VerseTarget) => void;
  onSaveVault?: (t: VerseTarget) => void;
}

interface WindowWithTestUrl {
  __JW_TEST_URL__?: string;
}

function getHref(): string {
  const override = (window as unknown as WindowWithTestUrl).__JW_TEST_URL__;
  return typeof override === "string" ? override : window.location.href;
}

async function getStoredVaultPath(): Promise<string | null> {
  if (typeof chrome === "undefined" || !chrome.storage?.local) return null;
  const data = await chrome.storage.local.get(["vault_path"]);
  return typeof data.vault_path === "string" ? data.vault_path : null;
}

async function getStoredLanguage(fallback: Language): Promise<Language> {
  if (typeof chrome === "undefined" || !chrome.storage?.local) return fallback;
  const data = await chrome.storage.local.get(["language"]);
  return (data.language as Language | undefined) ?? fallback;
}

function anchorOf(target: VerseTarget): HTMLElement {
  return (target.node.nextElementSibling as HTMLElement | null) ?? target.node;
}

function defaultHandlers(
  t: (key: string, params?: Record<string, string>) => string,
) {
  const api = new JwApiClient();

  return {
    onExplain: async (target: VerseTarget) => {
      const lang = await getStoredLanguage(detectLanguage(getHref()));
      const anchor = anchorOf(target);
      showTooltip(anchor, (tip) => {
        const em = document.createElement("em");
        em.textContent = `${t("action.explain")}…`;
        tip.appendChild(em);
      });
      try {
        const out = await api.verseMarkdown({
          reference: target.reference,
          language: lang,
          template: "callout",
        });
        showTooltipText(anchor, target.reference, out.markdown);
      } catch (err) {
        showToast(
          t("toast.error", {
            msg: err instanceof Error ? err.message : "unknown",
          }),
          "err",
        );
      }
    },
    onCrossRefs: async (target: VerseTarget) => {
      const lang = await getStoredLanguage(detectLanguage(getHref()));
      const anchor = anchorOf(target);
      showTooltip(anchor, (tip) => {
        const em = document.createElement("em");
        em.textContent = `${t("action.crossrefs")}…`;
        tip.appendChild(em);
      });
      try {
        const out = await api.crossRefs({
          reference: target.reference,
          language: lang,
        });
        showTooltipLinks(
          anchor,
          target.reference,
          out.refs.map((r) => ({
            label: r.verse,
            href: r.url,
            excerpt: r.excerpt,
          })),
        );
      } catch (err) {
        showToast(
          t("toast.error", {
            msg: err instanceof Error ? err.message : "unknown",
          }),
          "err",
        );
      }
    },
    onSaveVault: async (target: VerseTarget) => {
      const lang = await getStoredLanguage(detectLanguage(getHref()));
      const vaultPath = await getStoredVaultPath();
      if (!vaultPath) {
        showToast(
          t("toast.error", { msg: "vault path not configured" }),
          "err",
        );
        return;
      }
      try {
        const out = await api.vaultAppend({
          reference: target.reference,
          vault_path: vaultPath,
          template: "callout",
          language: lang,
        });
        if (out.ok) {
          showToast(t("toast.saved", { path: out.path }));
        } else {
          showToast(
            t("toast.error", { msg: out.error ?? "unknown" }),
            "err",
          );
        }
      } catch (err) {
        showToast(
          t("toast.error", {
            msg: err instanceof Error ? err.message : "unknown",
          }),
          "err",
        );
      }
    },
  };
}

export function run(opts: RunOpts = {}): void {
  const href = getHref();
  const ctx = buildReferenceFromUrl(href);
  if (!ctx) return;

  const lang = detectLanguage(href);
  const t = createTranslator(lang);
  const verses = detectVerses(document, ctx);
  if (verses.length === 0) return;

  const handlers = defaultHandlers(t);

  injectButtonsForVerses(verses, {
    onExplain: opts.onExplain ?? handlers.onExplain,
    onCrossRefs: opts.onCrossRefs ?? handlers.onCrossRefs,
    onSaveVault: opts.onSaveVault ?? handlers.onSaveVault,
    t,
  });

  // eslint-disable-next-line no-console
  console.info(`[jw-ext] injected ${verses.length} verse action(s)`);
}

function shouldBoot(): boolean {
  if (typeof window === "undefined") return false;
  if (window.location?.hostname === "wol.jw.org") return true;
  const override = (window as unknown as WindowWithTestUrl).__JW_TEST_URL__;
  return (
    typeof override === "string" && override.startsWith("https://wol.jw.org/")
  );
}

// Auto-run when bundled into the page. Vitest imports `run` directly so this
// is gated by `shouldBoot()`.
if (shouldBoot()) {
  if (
    document.readyState === "complete" ||
    document.readyState === "interactive"
  ) {
    run();
  } else {
    document.addEventListener("DOMContentLoaded", () => run());
  }
}
