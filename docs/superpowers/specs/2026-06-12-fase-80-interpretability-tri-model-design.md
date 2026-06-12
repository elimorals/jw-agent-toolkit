# Fase 80 — Interpretabilidad doctrinal tri-modelo (Gemma Scope + Qwen Scope + CoT auditable)

> **Fecha**: 2026-06-12
> **Estado**: Diseño en revisión
> **Owner**: Elias
> **Tier**: 3 (investigación + alineamiento profundo)
> **Capa**: D — interpretabilidad mecanicista
> **Depende de**: F77 principios YAML, F78 judge + preference dataset, F79 DPO/ORPO Qwen3.5-0.8B
> **Sucesor conceptual**: arquitectura de alineamiento doctrinal F77–F79
> **Predecesor inmediato**: gap detectado en F77–F79 — `jw_finetune.synth.critique.self_critique` (SL-CAI) está especificado pero no implementado

## Motivación

F77–F79 cerró el loop de alineamiento doctrinal:
principios YAML → judge oracle → preference dataset → DPO/ORPO en Qwen3.5-0.8B → `fidelity_wrap` en runtime. 1.326 tests verdes, formula del judge transparente, principios versionados.

Lo que **F77–F79 no responde** es la pregunta más importante para una IA con responsabilidad doctrinal:

> Cuando el modelo da una respuesta doctrinalmente correcta, ¿la da **por las razones correctas** o por un **shortcut estilístico** que detectó durante DPO (e.g. "responder con tono JW + citar publicaciones" sin que el contenido semántico de los 5 principios viva en la representación)?

Sin esa respuesta, no podemos:

1. **Auditar el razonamiento** del modelo durante CoT visible, capa por capa.
2. **Detectar drift doctrinal** cuando se re-entrena con corpus actualizado.
3. **Justificar guardrails causalmente**: hoy `fidelity_wrap` rechaza por regex/NLI; no podemos decir "rechazamos porque la feature PF001-canon-only no se activó".
4. **Reportar honestamente** a stakeholders externos qué aprendió y qué no.

El estado del arte para responder esto es **interpretabilidad mecanicista** vía probing lineal, steering vectors, activation patching y Sparse Autoencoders (SAEs). Anthropic demostró con "Scaling Monosemanticity" (Templeton et al., 2024) que SAEs pueden aislar features morales/axiológicas. Google DeepMind liberó **Gemma Scope** (JumpReLU SAEs en todas las capas y sitios) y el equipo Qwen liberó **Qwen-Scope** (TopK SAEs en residual stream).

Esta fase construye el subsistema de interpretabilidad sobre el alineamiento existente, **sin tocar producción**.

## Objetivos

1. **Cerrar el gap de SL-CAI** (`critique.self_critique`) — pipeline de auto-crítica contra los 5 principios. Es prerequisito de cualquier interpretabilidad porque mejora la señal de entrenamiento.
2. **Diagnóstico de representación** por principio: probe lineal de bajo coste que responde "¿PFxxx vive en la representación?".
3. **Validación causal** vía steering vectors contrastivos y activation patching: ¿la respuesta correcta depende causalmente del principio o solo de estilo?
4. **Lab de interpretabilidad profunda** con dos modelos en paralelo, no en producción:
   - Qwen3.5-2B-Base + **Qwen-Scope público** (misma familia que producción → transfer)
   - Gemma 2 2B IT + **Gemma Scope público** (instrumento SAE más maduro → ground truth interpretabilidad)
5. **Cross-family validation** de features morales: si un principio doctrinal emerge como feature en ambas familias, la afirmación es más fuerte que si solo emerge en una.
6. **CoT auditable doble**: el judge actual audita el texto del CoT (NLI por paso); las features SAE auditan qué activa el modelo en cada paso. Doble red de seguridad.
7. **Guardrails interpretables** en `fidelity_wrap` v2: rechazar findings por causa explícita (feature no activada / feature de shortcut activada), no solo por regex.

## No-objetivos (boundaries vinculantes)

- **No** se cambia el modelo de producción (Qwen3.5-0.8B fine-tuneado). El lab vive aparte.
- **No** se entrenan SAEs sobre el 0.8B. La literatura es clara: monosemanticity es pobre a esa escala. Los SAEs viven en los modelos de 2B del lab.
- **No** se reemplaza el judge oracle existente. SAEs son señal complementaria, no sustituto.
- **No** se publica nada externamente sin verificación causal. Una feature que correlaciona con un principio no es evidencia de que el modelo "razone" sobre él.
- **No** se persigue paridad con Anthropic/DeepMind. Es un proyecto individual con hardware limitado; el target es "auditoría defendible internamente", no paper de safety.
- **No** se conecta SAE features a una pipeline de re-entrenamiento automático. Eso es un nivel siguiente que requiere validación previa.

## Decisión 1: arquitectura tri-modelo (no mono-modelo)

### Opción A — Mono-modelo: SAE propio sobre Qwen3.5-0.8B fine-tuneado

Entrenar un SAE custom sobre el modelo de producción.

**Pros**: una sola fuente de verdad, integración directa con runtime.
**Contras**: a 0.8B la monosemanticity es pobre (literatura consistente: Anthropic, DeepMind y OpenAI entrenan SAEs sobre ≥2B); riesgo alto de feature hedging si corpus es estrecho; coste de entrenar SAE custom sin ground truth para validar.

### Opción B — Bi-modelo: lab en Qwen3.5-2B-Base + Qwen-Scope público

Usar Qwen3.5-2B-Base como espejo del 0.8B y aprovechar SAEs ya entrenados.

**Pros**: SAEs gratis, misma familia, transfer plausible al 0.8B.
**Contras**: Qwen-Scope solo cubre residual stream, no MLP/attn; TopK no es SOTA; Qwen-Scope para 2B-Base está sobre el **base model**, no sobre uno fine-tuneado con doctrina JW, lo cual limita su utilidad para auditar el modelo doctrinal específicamente.

### Opción C — Tri-modelo: producción Qwen 0.8B + lab Qwen 2B + lab Gemma 2B (recomendada)

Tres modelos con roles distintos.

- **Producción**: `Qwen3.5-0.8B` fine-tuneado DPO/ORPO. Sin cambios.
- **Lab Qwen**: `Qwen3.5-2B-Base` + **Qwen-Scope público** (`SAE-Res-Qwen3.5-2B-Base-W32K-L0_50`, 24 capas, residual, TopK=50, 32k features, expansion 16×). Misma familia tokenizer/arquitectura que el 0.8B → permite **transfer de hipótesis** entre modelos.
- **Lab Gemma**: `Gemma-2-2B` **base/PT** (no IT) fine-tuneado con SFT doctrinal desde base + **Gemma Scope público para `gemma-2-2b-pt`** (residual + MLP + attention, JumpReLU, 16k–262k features, todas las capas). Importante: Gemma Scope cubre 2B-PT completo; la única variante IT con SAEs es 9B-IT. Por eso fine-tuneamos desde PT — para aprovechar el ecosistema SAE completo. Familia distinta a Qwen → si una feature emerge aquí Y en Qwen, es ground truth mucho más fuerte.

**Pros**:
- Cero coste de entrenamiento de SAEs en el camino crítico — ambos ecosistemas SAE son públicos.
- Cross-family validation: features morales que coinciden entre dos arquitecturas distintas son evidencia robusta, no artefacto.
- Producción intocada: si los experimentos fallan, no pasa nada en runtime.
- Aprovecha tu RTX 5090 (32GB VRAM) — ambos 2B con SAEs caben con margen; el 0.8B de producción cabe junto en sesiones de probing.
- Permite escalar: si en Fase 4 emergen features útiles en Gemma Scope, pueden migrar a guardrails de producción vía probes lineales transferidos al 0.8B (no requiere correr SAE en producción).

**Contras**:
- Dos modelos de lab que mantener sincronizados con el corpus JW.
- Fine-tune doctrinal de Gemma-2-2B desde cero (no existe pipeline previo).
- Análisis SAE en dos familias = más trabajo de etiquetado de features.

**Decisión**: **Opción C**. La cross-family validation justifica el doble trabajo. Es la única que da evidencia causal robusta de que el modelo aprende los principios y no solo el estilo.

## Decisión 2: CoT visible como superficie auditada doble

CoT visible cambia drásticamente la geometría de auditoría:

```
Pregunta doctrinal del usuario
        │
        ▼
[CoT step 1]  ← audita texto (judge NLI) + audita activación SAE
[CoT step 2]  ← audita texto (judge NLI) + audita activación SAE
...
[CoT step N]  ← audita texto (judge NLI) + audita activación SAE
        │
        ▼
Respuesta final  ← `fidelity_wrap` actual (regex + NLI + principios)
```

Cada paso del CoT es:
- Una **proposición textual** auditable por el judge (`NLI` entailment vs principio).
- Una **traza de activación** capturable en hidden states → auditable por probes y SAEs en el lab, transferible como steering vector al 0.8B en producción.

Si una respuesta final pasa el judge pero el CoT muestra activaciones espurias (e.g. principio PF001 no se activa, pero sí activa "tono JW genérico"), tenemos evidencia de shortcut. Eso es lo que hoy no podemos detectar.

**Implicación de diseño**: el formato del CoT debe ser **estructurado** (steps numerados con tags semánticos) para que el judge pueda atribuir cada activación a un paso de razonamiento concreto. Esto requiere ajustar el chat template del modelo de producción y del lab Gemma para emitir CoT en formato consistente.

## Decisión 3: por qué Gemma Scope como primario y Qwen Scope como complementario

Aunque producción es Qwen, **Gemma Scope es el instrumento SAE de mayor calidad pública**:

| Dimensión | Gemma Scope | Qwen Scope |
|---|---|---|
| Sitios entrenados | residual + MLP out + attention out | solo residual |
| Cobertura por capa | TODAS las capas | TODAS las capas |
| Método | **JumpReLU** (SOTA en fidelity/sparsity tradeoff) | TopK fijo |
| Anchos disponibles | 16k → 1M features (multi-resolución) | 32k fijo |
| Auto-interp | Neuronpedia con etiquetas automáticas | sin Neuronpedia |
| Soporte SAELens | nativo (`gemma-scope-2b-pt-res`) | requiere wrapper manual |
| Variante IT | Gemma-2-9B-IT cubierta | solo Qwen3.5-27B-IT cubierta |
| Licencia | CC-BY-4.0 | Qwen license |

**Qwen Scope se queda** porque:
- Mismo tokenizer y familia arquitectónica que el 0.8B de producción → permite **transfer de probes y steering vectors** del lab Qwen 2B al modelo de producción con mucha menos pérdida que cross-family.
- Si Gemma Scope no tiene SAEs en una capa específica que necesitas (improbable) o si quieres comparar TopK vs JumpReLU como ablation, Qwen Scope sirve como segunda fuente.
- **Qwen-Scope sobre Qwen3.5-2B-Base** (verificado en HF: `SAE-Res-Qwen3.5-2B-Base-W32K-L0_50`) cubre las 24 capas en residual. Coincide con la arquitectura del 0.8B (también 24 capas en Qwen3.5).

## Arquitectura del sistema

```
┌────────────────────────────────────────────────────────────────────┐
│  CORPUS JW (extraído por jw-finetune)                              │
│  Atalayas + Study Notes + Workbooks + Bible + Theographic          │
└────────────────────────────────────────────────────────────────────┘
                 │
                 ├──→ SFT dataset (existente, F77 pre)
                 │
                 ├──→ Preference dataset (existente, F77)
                 │
                 └──→ NEW: SL-CAI critique dataset (Fase 0)
                              │
                              ▼
        ┌──────────────────────────────────────────────────┐
        │  ENTRENAMIENTO (3 RUTAS)                          │
        └──────────────────────────────────────────────────┘
              │                  │                  │
              ▼                  ▼                  ▼
    ┌──────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
    │ PRODUCCIÓN       │ │ LAB QWEN        │ │ LAB GEMMA           │
    │ Qwen3.5-0.8B     │ │ Qwen3.5-2B-Base │ │ Gemma-2-2B-IT       │
    │ SFT+DPO+ORPO     │ │ SFT-only        │ │ SFT-only            │
    │ +SL-CAI (F0)     │ │ (matched corpus)│ │ (matched corpus)    │
    │ CoT estructurado │ │ CoT estructurado│ │ CoT estructurado    │
    └──────────────────┘ └─────────────────┘ └─────────────────────┘
              │                  │                  │
              │                  ▼                  ▼
              │       ┌──────────────────┐ ┌─────────────────────┐
              │       │ Qwen-Scope SAE   │ │ Gemma Scope SAE     │
              │       │ residual L0–L23  │ │ residual + MLP+attn │
              │       │ TopK=50, 32k     │ │ JumpReLU, 16k–262k  │
              │       │ (público)        │ │ (público)           │
              │       └──────────────────┘ └─────────────────────┘
              │                  │                  │
              │                  └────────┬─────────┘
              │                           ▼
              │              ┌──────────────────────────────┐
              │              │ FEATURE DISCOVERY            │
              │              │ • Auto-interp (Neuronpedia + │
              │              │   Claude judge)              │
              │              │ • Max-activating examples    │
              │              │   sobre prompts etiquetados  │
              │              │   por principio PF001-PF012  │
              │              │ • Cross-family agreement     │
              │              │   matrix                     │
              │              └──────────────────────────────┘
              │                           │
              │                           ▼
              │              ┌──────────────────────────────┐
              │              │ CAUSAL VALIDATION            │
              │              │ • Activation patching        │
              │              │ • Feature ablation           │
              │              │ • Steering vector contrast   │
              │              └──────────────────────────────┘
              │                           │
              │                           ▼
              │              ┌──────────────────────────────┐
              │              │ TRANSFER A PRODUCCIÓN        │
              │              │ • Probes lineales en 0.8B    │
              │              │   sobre las features         │
              │              │   validadas                   │
              │              │ • Steering vectors derivados  │
              │              └──────────────────────────────┘
              │                           │
              ▼                           ▼
    ┌──────────────────────────────────────────────────────┐
    │  RUNTIME: fidelity_wrap v2                            │
    │  • Tier 1 (existente): regex + violations_for         │
    │  • Tier 2 (existente): NLI por paso CoT               │
    │  • Tier 3 (existente): judge oracle                   │
    │  • Tier 4 (NUEVO): probes lineales / steering          │
    │    derivados del lab → causa interpretable            │
    └──────────────────────────────────────────────────────┘
```

## Fase 0 — SL-CAI `self_critique` (1 semana)

**Por qué primero**: gap detectado en F77–F79, mueve la aguja del alineamiento real más que cualquier interpretabilidad. Y produce **señal de entrenamiento adicional** que beneficia las fases siguientes.

**Tareas**:
1. Implementar `jw_finetune/synth/critique/self_critique.py`:
   - `critique(question, draft_answer, principles, language) → CritiqueResult` con:
     - violations detectadas (heurística + LLM judge),
     - `revised_answer` reescrita corrigiendo violaciones,
     - `reasoning_chain` (CoT del critique mismo).
2. Integrar en CLI: `jw-finetune build-critique-dataset` que toma el SFT dataset, genera draft, crítica, y produce un dataset `(prompt, draft, critique, revised)` apto para SFT-CAI.
3. Tests: 10+ tests cubriendo cada principio + edge cases (sin violación, soft violation, hard violation, NLI contradiction, no citation).
4. Documentar en `docs/guias/sl-cai.md`.

**Criterios de éxito**:
- Pipeline produce críticas que `judge.score_pair(draft, revised)` puntúa `revised` como mejor en ≥80% de casos donde la `draft` tenía violación.
- Reduce hard violations en el dataset de entrenamiento del próximo SFT round ≥50%.
- 0 regresiones en los 1.326 tests existentes.

## Fase 1 — Probing lineal por principio (1.5 semanas)

**Objetivo**: respuesta barata y honesta a "¿los 5 principios viven en la representación del 0.8B?".

**Tareas**:
1. Crear `packages/jw-interp/` (nuevo paquete del monorepo).
2. Construir dataset de probing: para cada PF (PF001, PF002, PF003, PF010, PF012) generar ~500 pares contrastivos `(prompt_que_invoca_principio, prompt_neutral)` con labels.
3. Para cada principio:
   - Capturar activaciones residuales en las 24 capas del 0.8B fine-tuneado vía nnsight (no requiere port a TransformerLens).
   - Entrenar probe lineal binario (logistic regression con sklearn) sobre activaciones de cada capa.
   - Reportar accuracy + AUC por capa.
4. Visualización: heatmap (5 principios × 24 capas) de probe accuracy.
5. Repeat sobre Qwen3.5-2B-Base SFT y Gemma-2-2B-IT SFT — comparar dónde emerge cada principio.

**Criterios de éxito**:
- Probe accuracy ≥0.80 en al menos una capa para cada principio. Si ≥0.90 → principio "está claro" en la representación. Si ≤0.70 → shortcut sospechoso, alerta.
- Reporte `docs/superpowers/specs/2026-XX-XX-fase-80-1-probing-report.md` con conclusiones por principio.

## Fase 2 — Steering vectors + activation patching (2 semanas)

**Objetivo**: validación **causal**, no solo correlacional. Si el probe encuentra la feature pero la activación no causa la conducta, es shortcut.

**Tareas**:
1. Para cada principio, calcular **steering vector** como `mean(activations | principio_invocado) − mean(activations | neutral)` en la capa de máxima accuracy del probe.
2. Steering experiments en el 0.8B:
   - Sumar +α·vector → ¿respuesta más fiel al principio?
   - Restar −α·vector → ¿respuesta rompe el principio?
   - Si no rompe al restar, no es causal.
3. **Activation patching contrastivo**: prompt A (respuesta-fundada) vs prompt B (respuesta-shortcut con mismo prefix). Patch capa por capa. La capa donde el patching cambia la salida es la capa decisiva.
4. Documentar matrix `(principio × {steering+, steering−, patching}) → conclusión causal`.
5. Replicar en lab Qwen 2B y lab Gemma 2B (validación cross-model).

**Criterios de éxito**:
- ≥4 de 5 principios muestran efecto causal (no solo correlacional) en al menos una de las 3 técnicas.
- Si <3 muestran efecto causal → alerta seria: el DPO está aprendiendo estilo, no semántica. Revisar dataset.

## Fase 3 — Qwen-Scope sobre Qwen3.5-2B-Base (2 semanas)

**Objetivo**: usar SAEs reales para descubrir features morales en familia Qwen.

**Tareas**:
1. Descargar `Qwen/SAE-Res-Qwen3.5-2B-Base-W32K-L0_50` (24 archivos `.pt`, uno por capa).
2. Adapter en `jw-interp/qwen_scope.py`: load SAE, hook a Qwen3.5-2B-Base SFT-doctrinal, extraer features TopK por prompt.
3. Para cada principio:
   - Construir 500 prompts etiquetados por PF.
   - Capturar features activadas top-K en capas mid (L8, L12, L16, L20).
   - Auto-interp con Claude Opus (función `interpret_feature(top_examples) → label`).
   - Filtrar features cuyas labels contienen "doctrina", "canon", "citation", "conscience", etc.
4. Construir **mapa principio → features SAE** con scores de overlap.
5. Causal: ablar features candidatas (cero en encode) y medir cambio en la conducta del modelo. Si la conducta cambia → causal. Si no → spurious correlation.

**Criterios de éxito**:
- ≥3 features por principio con auto-interp coherente Y efecto causal en ablation.
- Las features encontradas son **diferentes** de las features del modelo base sin fine-tune (control negativo): el fine-tune doctrinal debe inducir nuevas features, no solo amplificar las existentes.

## Fase 4 — Gemma Scope sobre Gemma-2-2B-PT fine-tuneado (3 semanas)

**Objetivo**: validación cross-family + nivel de detalle superior (MLP + attention + JumpReLU).

**Tareas**:
1. Fine-tune `google/gemma-2-2b` (PT/base) con SFT sobre el mismo corpus doctrinal usado en Qwen lab. Trabajamos desde PT por dos razones: (a) preserva la compatibilidad con Gemma Scope completo, (b) nos da control total del chat template e instruction-following sin heredar el alignment de Google que podría interferir con la doctrina JW.
   - Recipe nueva en `jw-finetune`: `doctrinal-qa-es-sft-gemma2-2b-pt`.
   - Chat template custom Gemma (ChatML-like) con tags de CoT estructurado.
   - Dataset SFT incluye ~10% de ejemplos de instruction-following genéricos para no perder esa capacidad durante el doctrinal-SFT.
   - Validar paridad mínima: el Gemma fine-tuneado debe pasar ≥70% de los tests de doctrina del judge (no necesita ser tan bueno como Qwen — su rol es lab, no producción).
2. Integrar Gemma Scope vía SAELens (soporte nativo):
   - `SAE.from_pretrained("gemma-scope-2b-pt-res-canonical", sae_id="layer_{N}/width_16k/canonical")` para residual.
   - `gemma-scope-2b-pt-mlp-canonical` para MLP out.
   - `gemma-scope-2b-pt-att-canonical` para attention out.
   - Tres sitios disponibles en TODAS las capas, distinto a Qwen Scope (solo residual).
3. Pipeline de feature discovery (idem Fase 3 pero con más superficie):
   - residual stream (compara con Qwen Scope) + MLP (lógica de transformación) + attention (qué atiende el modelo en cada capa al hablar de un principio).
4. **Cross-family agreement matrix**: por cada principio, ¿se activan features semánticamente equivalentes en Qwen Scope y Gemma Scope?
5. **Notebook de exploración** basado en el Colab oficial de Gemma Scope adaptado a tu corpus JW: `notebooks/gemma_scope_jw_features.ipynb`.

**Criterios de éxito**:
- Para ≥3 de 5 principios: feature equivalente identificada en ambas familias con auto-interp coherente.
- Causal validation en Gemma Scope (ablation + steering) muestra mismo signo de efecto que Qwen Scope para los principios coincidentes.
- Si las features no coinciden cross-family → o (a) el principio es muy específico al fine-tune doctrinal Qwen y no transferible, o (b) el principio es un shortcut. Ambas conclusiones son valiosas.

## Fase 5 (bonus) — Transfer al 0.8B y guardrails interpretables (2 semanas)

**Objetivo**: cerrar el loop con producción. Convertir hallazgos del lab en señal usable en runtime sin correr SAEs en producción.

**Tareas**:
1. Para cada principio con feature validada en lab:
   - Extraer steering vector del lab Qwen 2B.
   - Transferir al 0.8B vía proyección (capa mid Qwen 2B → capa mid Qwen 0.8B; dimensiones difieren pero el espacio semántico es relacionable).
   - Validar que el steering vector transferido también altera causalmente la conducta del 0.8B.
2. Entrenar probe lineal **definitivo** en el 0.8B (capa con mejor performance de Fase 1) sobre la feature confirmada en lab.
3. Integrar en `fidelity_wrap` como Tier 4:
   - Por cada finding generado, evaluar probes de los 5 principios sobre activaciones del CoT.
   - Si `probe(PF00X) < threshold` → flag interpretable: "el principio PFxxx no se activó en el razonamiento del modelo".
   - Esto es **complementario** al regex/NLI/judge, no sustituto.
4. Documentar en `docs/guias/interpretabilidad-runtime.md`.

**Criterios de éxito**:
- Probes en producción agregan <50ms de latencia por inferencia (medido). Inaceptable si más.
- Reducción ≥20% en false-positives del judge (casos donde el judge rechaza por razones espurias y el probe confirma que el principio sí estaba activado, o viceversa).
- 0 regresiones en tests existentes.

## Stack técnico

- **SAELens** (`pip install sae-lens`) — load Gemma Scope nativo, training de SAEs custom si se decide después.
- **nnsight** (`pip install nnsight`) — intervenciones causales sobre cualquier modelo HF sin port a TransformerLens. Único stack viable para Qwen3.5 fine-tuneado.
- **torch nativo** para Qwen Scope (los `.pt` se cargan directo con `torch.load`).
- **TransformerLens** opcional, solo si necesitas circuits-level analysis (no en el plan).
- **Neuronpedia API** para Gemma Scope auto-interp y exploración interactiva.
- **Claude Opus** como judge de auto-interp (re-uso del proveedor existente).
- **Existente del monorepo**: jw-eval principios, jw-finetune judge, jw-agents fidelity_wrap. Todo se integra, nada se reemplaza.

## Hardware por fase

- Fase 0–2: RTX 5090 local (probes y steering son baratos).
- Fase 3: RTX 5090 (Qwen-Scope son TopK simples, no requieren training).
- Fase 4: RTX 5090 para análisis; H100 fallback para fine-tune Gemma-2-2B (~12 horas A100 estimado, $25–40).
- Fase 5: RTX 5090 + medición de latencia en Mac Metal (target real de producción).

## Métricas de éxito globales

| Métrica | Baseline | Target |
|---|---|---|
| Hard violations en dataset entrenamiento | F79 actual | −50% post Fase 0 |
| Principios con representación clara (probe ≥0.80) | desconocido | ≥4 de 5 (Fase 1) |
| Principios con efecto causal (steering/patching/ablation) | desconocido | ≥4 de 5 (Fase 2) |
| Principios con features SAE coincidentes cross-family | desconocido | ≥3 de 5 (Fase 4) |
| False-positives `fidelity_wrap` reducidos | actual | −20% (Fase 5) |
| Latencia añadida en runtime por Tier 4 | 0ms | <50ms p95 |
| Tests verdes | 1.326 | ≥1.500 al final |

## Riesgos y mitigaciones

1. **Features SAE polysemánticas a 2B**: posible que las features no sean monosemánticas y la auto-interp falle.
   - *Mitigación*: usar Gemma Scope variante "wide" (262k features) cuando la "canonical" (16k) sea pobre. Comparar varias resoluciones.

2. **Cross-family transfer falla**: las features que emergen en Qwen pueden no emerger en Gemma o viceversa.
   - *Mitigación*: ese resultado mismo es informativo. Si un principio solo emerge en una familia, sospechamos artefacto. Continúa con los principios que sí cruzan.

3. **Fine-tune de Gemma para JW resulta peor que Qwen**: posible que Gemma no aprenda el dominio doctrinal con la misma calidad y los SAEs reflejen un modelo "que no sabe".
   - *Mitigación*: criterio de admisión es 70% de tests de doctrina, no paridad. Si no llega, escalar a `gemma-2-9b` (base/PT) con Gemma Scope 9B residual/MLP/attn que también existe (más caro pero viable con H100 fallback).

4. **Feature hedging (paper 2026)**: SAEs entrenados con corpus estrecho rompen representaciones.
   - *Mitigación*: SAEs Gemma/Qwen Scope se entrenaron sobre corpus generales, no JW. El riesgo aplica solo si entrenamos SAE custom — explícitamente fuera de scope de esta fase.

5. **CoT estructurado degrada calidad de generación**: forzar formato puede reducir naturalidad.
   - *Mitigación*: A/B en F0 entre CoT estructurado y CoT libre. Mantener el modo que mejor puntúa en judge.

6. **Latencia de Tier 4 inaceptable**: probes lineales sobre 24 capas pueden agregar overhead.
   - *Mitigación*: probes solo en 3–4 capas decisivas identificadas en Fase 1. Si aún así >50ms, mover Tier 4 a modo async (auditoría posterior) en vez de bloqueante.

7. **Drift entre 0.8B producción y 2B lab**: al re-entrenar producción cambian los features.
   - *Mitigación*: protocolo de re-validación: cada nueva versión del 0.8B debe pasar el suite de probes antes de publicarse.

## Gaps y dependencias

- **Bloqueador F0**: SL-CAI critique no existe. Implementación es prerequisito.
- **Bloqueador F4**: no hay receta SFT para Gemma-2-2B en `jw-finetune`. Hay que añadirla.
- **No bloqueador, pero útil**: una futura fase tipo `doctrinal-rollback` sería complementaria para versionar features detectadas entre re-entrenamientos del 0.8B — fuera de scope.
- **No bloqueador, pero conveniente**: usuario de Hugging Face con acceso aceptado a `google/gemma-2-2b` (gating de Google). Si no lo tienes, F4 se retrasa hasta tenerlo.

## Próximos pasos inmediatos

1. **Aprobación del spec** (este documento).
2. **Plan de implementación** Fase 0 vía `superpowers:writing-plans` skill.
3. **Issue tracker** o tasks en el repo correspondiente a cada fase con criterios de aceptación.
4. **Validación de hardware**: confirmar acceso H100/B200 fallback (cuál proveedor, cómo se accede).
5. **HF gating**: solicitar acceso a `google/gemma-2-2b-it` si no se tiene.

## Referencias

- Gemma Scope paper — Lieberum et al., 2024 — https://arxiv.org/abs/2408.05147
- Qwen-Scope paper — https://arxiv.org/abs/2605.11887
- Scaling Monosemanticity — Templeton et al., 2024 — https://transformer-circuits.pub/2024/scaling-monosemanticity/
- JumpReLU SAE — Rajamanoharan et al., 2024 — https://arxiv.org/abs/2407.14435
- SAEs Do Not Find Canonical Units — Leask et al., ICLR 2025 — https://arxiv.org/abs/2502.04878
- Feature Hedging — 2026 — https://arxiv.org/abs/2505.11756
- Gemma Scope Colab — https://colab.research.google.com/drive/17dQFYUYnuKnP6OwQPH9v_GSYUW5aj-Rp
- Gemma Scope HF — https://huggingface.co/google/gemma-scope
- Qwen-Scope 2B-Base HF — https://huggingface.co/Qwen/SAE-Res-Qwen3.5-2B-Base-W32K-L0_50
- SAELens — https://github.com/decoderesearch/SAELens
- nnsight — https://nnsight.net/
