from abc import ABC, abstractmethod
from typing import List
from universal_playlists.matcher import MatcherStrategy
from universal_playlists.services.services import Searchable

from universal_playlists.track import Track


class SearcherStrategy(ABC):
    @abstractmethod
    def search(self, service: Searchable, track: Track) -> List[Track]:
        """Search for a track in the streaming service.
        Returns a sorted list of potential matches."""


class DefaultSearcherStrategy(SearcherStrategy):
    matcher: MatcherStrategy

    def __init__(self, matcher: MatcherStrategy) -> None:
        self.matcher = matcher

    def search(self, service: Searchable, track: Track) -> List[Track]:
        queries = service.query_generator(track)
        stop_threshold = 0.8
        matches = []

        for query in queries:
            results = service.search_query(query)
            matches.extend(results)
            if any(
                self.matcher.similarity(track, match) >= stop_threshold
                for match in results
            ):
                break

        matches.sort(key=lambda t: self.matcher.similarity(track, t), reverse=True)
        return matches