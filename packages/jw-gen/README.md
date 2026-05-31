# jw-gen

Generative-content toolkit (image / audio / video) for **personal illustrative** use in
JW-context presentations and personal talks.

**Approved policy (load-bearing):**
> Solo personal/ilustrativo + presentaciones/discursos. Watermark obligatorio.
> NO emulación contenido oficial JW.

Every file written to disk receives:
- Visible watermark (Pillow rasterization).
- EXIF + XMP metadata identifying the file as `jw-gen` output with prompt hash + provider.
- Sibling `*.disclaimer.txt` in en / es / pt explaining personal-use scope.

Three non-negotiable safety filters run **before** any provider call:
- `refuse_jw_logo_emulation` — hard refuse, no opt-in.
- `refuse_voice_cloning_without_double_optin` — flag + signed consent file + interactive confirm.
- `refuse_realistic_faces_without_optin` — default stylized, `--realistic-people` to opt in.

Run: `jw gen image --prompt "..." --out out.png`.
Spec: `docs/superpowers/specs/2026-05-31-fase-38-jw-gen-design.md`.
