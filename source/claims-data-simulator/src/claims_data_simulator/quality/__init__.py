"""Data quality injection for the claims simulator.

Applies response-only mutations such as duplicate rows and nulled patient
IDs to exercise downstream data-quality handling without corrupting
persisted state.
"""
