"""Concrete NLIProvider implementations.

Each provider lives in its own module so optional deps (transformers,
anthropic, openai) can be imported lazily and CI hosts without those
deps still install ``jw-core`` cleanly.
"""
