"""HTTP API layer.

Routers are thin: they translate requests into ``StateStore`` calls and return
persisted models. No trading logic lives here — the store owns truth.
"""
