"""Layer 2 — Learning platform.

This package owns the learning-domain logic that sits above the generic
conversation engine (Layer 1a/1b) but below school-level orchestration
(Layer 3). It reads from the Layer 1b SlotResolver port and registers
hooks/callbacks with the Layer 1b service.
"""
