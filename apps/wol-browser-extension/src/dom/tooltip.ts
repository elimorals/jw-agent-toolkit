/**
 * Floating tooltip anchored under an element. Single instance reused.
 * Closes on outside click or Esc.
 *
 * IMPORTANT: this module deliberately avoids ``innerHTML`` with arbitrary
 * strings. The two public surface APIs are:
 *
 *   - ``showTooltip(anchor, builder)`` where ``builder`` is a function the
 *     caller uses to populate a fresh ``HTMLElement`` with safe DOM nodes.
 *   - ``showTooltipText(anchor, title, body)`` for the common "title + plain
 *     text body" path.
 *
 * This keeps tooltip contents free of XSS: even when the body comes from the
 * local toolkit's REST response, the response is rendered Markdown that we
 * insert as ``textContent`` inside a ``<pre>`` — never parsed as HTML.
 */

let current: HTMLElement | null = null;
let escHandler: ((e: KeyboardEvent) => void) | null = null;
let clickHandler: ((e: MouseEvent) => void) | null = null;

function cleanup(): void {
  if (current && current.parentNode) {
    current.parentNode.removeChild(current);
  }
  current = null;
  if (escHandler) {
    document.removeEventListener("keydown", escHandler);
    escHandler = null;
  }
  if (clickHandler) {
    document.removeEventListener("click", clickHandler, true);
    clickHandler = null;
  }
}

function position(tip: HTMLElement, anchor: HTMLElement): void {
  const rect = anchor.getBoundingClientRect();
  const top = rect.bottom + window.scrollY + 6;
  const left = Math.max(8, rect.left + window.scrollX);
  tip.style.top = `${top}px`;
  tip.style.left = `${left}px`;
}

function attachListeners(tip: HTMLElement, anchor: HTMLElement): void {
  escHandler = (e: KeyboardEvent) => {
    if (e.key === "Escape") cleanup();
  };
  clickHandler = (e: MouseEvent) => {
    if (!tip.contains(e.target as Node) && e.target !== anchor) cleanup();
  };
  document.addEventListener("keydown", escHandler);
  document.addEventListener("click", clickHandler, true);
}

/**
 * Show a tooltip whose contents are produced by `build(tip)`. The caller
 * appends safe DOM nodes (textContent + createElement); the helper never
 * parses strings as HTML.
 */
export function showTooltip(
  anchor: HTMLElement,
  build: (tip: HTMLElement) => void,
): HTMLElement {
  cleanup();
  const tip = document.createElement("div");
  tip.className = "jw-ext-tooltip";
  build(tip);
  document.body.appendChild(tip);
  position(tip, anchor);
  attachListeners(tip, anchor);
  current = tip;
  return tip;
}

/** Show a tooltip with a heading + a plain-text body (rendered in a `<pre>`). */
export function showTooltipText(
  anchor: HTMLElement,
  title: string,
  body: string,
): HTMLElement {
  return showTooltip(anchor, (tip) => {
    const h = document.createElement("h3");
    h.textContent = title;
    tip.appendChild(h);
    const pre = document.createElement("pre");
    pre.textContent = body;
    pre.className = "jw-ext-tooltip-pre";
    tip.appendChild(pre);
  });
}

/** Show a tooltip with a heading + a list of (label, href) links. */
export function showTooltipLinks(
  anchor: HTMLElement,
  title: string,
  links: Array<{ label: string; href: string; excerpt?: string }>,
): HTMLElement {
  return showTooltip(anchor, (tip) => {
    const h = document.createElement("h3");
    h.textContent = title;
    tip.appendChild(h);
    if (links.length === 0) {
      const em = document.createElement("em");
      em.textContent = "—";
      tip.appendChild(em);
      return;
    }
    const ul = document.createElement("ul");
    for (const link of links) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = link.href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = link.label;
      li.appendChild(a);
      if (link.excerpt) {
        li.appendChild(document.createTextNode(`: ${link.excerpt}`));
      }
      ul.appendChild(li);
    }
    tip.appendChild(ul);
  });
}

export function hideTooltip(): void {
  cleanup();
}

export function showToast(message: string, kind: "ok" | "err" = "ok"): void {
  const t = document.createElement("div");
  t.className = `jw-ext-toast jw-ext-toast-${kind}`;
  t.textContent = message;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add("jw-ext-toast-visible"), 10);
  setTimeout(() => {
    t.classList.remove("jw-ext-toast-visible");
    setTimeout(() => t.remove(), 300);
  }, 3500);
}
