"""Domain services: message delivery and its audit trail.

Services are deliberately free of HTTP concerns so they can be unit-tested and
reused by other transports (CLI, queue worker, ...).
"""
