"""
Package data_mining : Moteur SQL déterministe pour StatsBomb.
"""

from src.data_mining.db_connection import ReadOnlyDBConnection, SQLSecurityError
from src.data_mining.match_miner import MatchMiner

__all__ = [
    "ReadOnlyDBConnection",
    "SQLSecurityError",
    "MatchMiner",
]
