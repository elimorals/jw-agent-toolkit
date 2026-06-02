/**
 * Text normalization helpers ported from `jw_core.parsers.reference._norm`.
 *
 * `norm`:
 *   - lowercases
 *   - strips Unicode combining marks (so "Génesis" → "genesis", "João" → "joao")
 *   - preserves spaces, digits, punctuation
 *
 * `normKey`:
 *   - applies `norm` then collapses whitespace, dots, and hyphens
 *   - used as the index key so "1 Corintios", "1Corintios", "1.Corintios" all
 *     collide on the same bucket
 */

export function norm(input: string): string {
  return input
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}+/gu, "");
}

const KEY_CLEAN = /[\s.\-]+/g;

export function normKey(input: string): string {
  return norm(input).replace(KEY_CLEAN, "");
}

/**
 * Escape a literal string for use inside a RegExp pattern.
 */
export function escapeRegex(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
