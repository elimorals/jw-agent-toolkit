import type { VerseTarget } from "../types";

export interface ButtonHandlers {
  onExplain: (target: VerseTarget) => void;
  onCrossRefs: (target: VerseTarget) => void;
  onSaveVault: (target: VerseTarget) => void;
  t: (key: string) => string;
}

const SENTINEL_CLASS = "jw-ext-verse-actions";
const MARK_ATTR = "data-jw-ext-decorated";

function makeButton(opts: {
  cls: string;
  label: string;
  emoji: string;
  onClick: () => void;
}): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  b.className = `jw-ext-btn ${opts.cls}`;
  b.setAttribute("aria-label", opts.label);
  b.title = opts.label;
  b.textContent = opts.emoji;
  b.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    opts.onClick();
  });
  return b;
}

export function injectButtonsForVerses(
  verses: VerseTarget[],
  handlers: ButtonHandlers,
): void {
  for (const target of verses) {
    if (target.node.getAttribute(MARK_ATTR) === "1") continue;
    target.node.setAttribute(MARK_ATTR, "1");

    const wrap = document.createElement("span");
    wrap.className = SENTINEL_CLASS;
    wrap.setAttribute("data-verse", String(target.verseNum));
    wrap.setAttribute("data-reference", target.reference);

    wrap.append(
      makeButton({
        cls: "jw-ext-btn-explain",
        label: handlers.t("action.explain"),
        emoji: "📖",
        onClick: () => handlers.onExplain(target),
      }),
      makeButton({
        cls: "jw-ext-btn-crossrefs",
        label: handlers.t("action.crossrefs"),
        emoji: "🔗",
        onClick: () => handlers.onCrossRefs(target),
      }),
      makeButton({
        cls: "jw-ext-btn-vault",
        label: handlers.t("action.save_vault"),
        emoji: "📝",
        onClick: () => handlers.onSaveVault(target),
      }),
    );

    target.node.insertAdjacentElement("afterend", wrap);
  }
}
