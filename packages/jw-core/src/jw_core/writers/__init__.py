"""Writers — inverse of `jw_core.parsers`.

Each parser in `jw_core.parsers` knows how to read a JW format; each writer
here knows how to produce one. Currently:

  - `writers.jwpub` — assemble a `.jwpub` from documents + media (Phase 49,
    ports `darioragusa/html2jwpub`, MIT).
"""
