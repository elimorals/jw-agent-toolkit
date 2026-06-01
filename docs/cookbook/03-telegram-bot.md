# Bot de Telegram sobre el REST API

> **Tiempo estimado**: 10 minutos
> **Requisitos**: REST API local (`jw mcp serve` o equivalente).
> **Slug URL**: `/cookbook/03-telegram-bot`

## ¿Qué construyes?

Un bot de Telegram que recibe mensajes, consulta el REST API local de `jw-mcp` y responde con findings + citations. El test verifica el pipeline de procesamiento de mensaje sin tocar Telegram ni red real.

## Código (copy-pasteable)

```python
# test
def process_message(text: str) -> str:
    """Pure function: receives a user message and returns the reply.

    Real bots wrap this with python-telegram-bot's handlers. Tested
    in isolation here so CI stays network-free.
    """
    # In production this would call POST localhost:8765/api/v1/verse_markdown.
    # For the test we simulate the response.
    fake_reply = {
        "findings": [
            {"text": "Porque Dios amó tanto al mundo", "citation": "Juan 3:16"},
        ],
    }
    if "/" in text or "verse" in text.lower():
        return fake_reply["findings"][0]["citation"]
    return "No entendí. Envía 'verse' o un comando '/'."

assert process_message("/start") == "Juan 3:16"
assert "No entendí" in process_message("hola")
```

## Por qué funciona

Mantener la lógica de respuesta **fuera del handler de Telegram** es el patrón que hace los bots testeables. El handler real solo es 5 líneas: recibe, llama `process_message`, envía. Toda la complejidad vive en la función pura.

## Variaciones

- Conectar a Claude vía Anthropic API y resumir findings antes de responder.
- Usar `parse_reference` (receta 01) para detectar citas en el mensaje.
- Limitar a usuarios autorizados con whitelist.

## Próximo paso

→ [04 — Fine-tune Llama 3](04-finetune-llama-3.md)
