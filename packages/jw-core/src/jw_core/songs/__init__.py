"""Kingdom Songs metadata registry (no lyrics).

Public API:
    from jw_core.songs import KingdomSong, SongLookupError, SongRegistry, get_registry
"""

from jw_core.songs.integration import enrich_with_songs
from jw_core.songs.models import KingdomSong, SongLookupError
from jw_core.songs.registry import SongRegistry, get_registry

__all__ = [
    "KingdomSong",
    "SongLookupError",
    "SongRegistry",
    "enrich_with_songs",
    "get_registry",
]
