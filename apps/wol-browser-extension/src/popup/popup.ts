import { createTranslator } from "../i18n";
import type { Language } from "../types";

interface Settings {
  vault_path: string;
  language: Language;
}

async function loadSettings(): Promise<Settings> {
  const data = await chrome.storage.local.get(["vault_path", "language"]);
  return {
    vault_path: typeof data.vault_path === "string" ? data.vault_path : "",
    language: (data.language as Language | undefined) ?? "en",
  };
}

export async function savePopupSettings(s: Settings): Promise<void> {
  await chrome.storage.local.set({
    vault_path: s.vault_path,
    language: s.language,
  });
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Partial<Record<string, string>> = {},
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v !== undefined) node.setAttribute(k, v);
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

export async function renderPopup(
  root: HTMLElement,
  lang: Language,
): Promise<void> {
  const current = await loadSettings();
  const effectiveLang = (current.language || lang) as Language;
  const t = createTranslator(effectiveLang);

  // Clear and rebuild via safe DOM APIs (no innerHTML with arbitrary strings).
  while (root.firstChild) root.removeChild(root.firstChild);

  root.appendChild(el("h1", {}, t("popup.title")));

  root.appendChild(el("label", { for: "vault_path" }, t("popup.vault_path")));
  const vaultInput = el("input", {
    id: "vault_path",
    type: "text",
    placeholder: t("popup.vault_path_placeholder"),
  });
  vaultInput.value = current.vault_path;
  root.appendChild(vaultInput);

  root.appendChild(el("label", { for: "language" }, t("popup.language")));
  const langSelect = el("select", { id: "language" });
  for (const [code, label] of [
    ["en", "English"],
    ["es", "Español"],
    ["pt", "Português"],
  ] as const) {
    const opt = el("option", { value: code }, label);
    if (effectiveLang === code) opt.selected = true;
    langSelect.appendChild(opt);
  }
  root.appendChild(langSelect);

  const testBtn = el("button", { id: "test" }, t("popup.test_connection"));
  root.appendChild(testBtn);
  const saveBtn = el("button", { id: "save" }, t("popup.save"));
  root.appendChild(saveBtn);

  const status = el("div", { id: "status", class: "status" });
  root.appendChild(status);

  testBtn.addEventListener("click", async () => {
    status.textContent = "…";
    status.className = "status";
    const resp = await chrome.runtime.sendMessage({ kind: "health" });
    if (resp?.ok) {
      status.textContent = t("popup.toolkit_ok");
      status.className = "status status-ok";
    } else {
      status.textContent = t("popup.toolkit_off");
      status.className = "status status-err";
    }
  });

  saveBtn.addEventListener("click", async () => {
    const vault = vaultInput.value.trim();
    const language = langSelect.value as Language;
    await savePopupSettings({ vault_path: vault, language });
    status.textContent = t("popup.saved");
    status.className = "status status-ok";
  });
}

// Boot when used as the actual popup (skipped in unit tests).
if (typeof window !== "undefined" && document.getElementById("root")) {
  const browserLang = (navigator.language ?? "en").slice(0, 2) as Language;
  void renderPopup(document.getElementById("root")!, browserLang);
}
