"""Streamlit cockpit — a thin, disposable UI client.

It owns no business logic and never talks to Alpaca. Every screen reads fresh
from the FastAPI backend on render, and every action is a backend API call
(see ``docs/01_ARCHITECTURE.md``: "Streamlit owns / must NOT own"). The only
state it keeps is view state (which screen is selected, form drafts).
"""
