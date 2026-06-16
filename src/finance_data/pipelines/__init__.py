"""Prefect-Flows je Asset-Klasse.

Pro Asset-Klasse ein Flow:
    extract → validate_raw → transform → validate_clean → upsert

Asset-Klassen (aus AGENTS.md):
- equities, indexes, gov_bonds, credit, money_market,
  commodities, fx, volatility, macro
"""
