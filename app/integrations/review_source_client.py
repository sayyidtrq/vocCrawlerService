from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.models import Location


class ReviewSourceError(RuntimeError):
    def __init__(self, message: str, retriable: bool = False):
        super().__init__(message)
        self.retriable = retriable


class ReviewSourceClient(ABC):
    @abstractmethod
    def fetch_reviews(
        self,
        location: Location,
        limit: int = 50,
        **kwargs,
    ) -> list[dict]:
        raise NotImplementedError


class UnsupportedReviewClient(ReviewSourceClient):
    def __init__(self, message: str):
        self.message = message

    def fetch_reviews(
        self,
        location: Location,
        limit: int = 50,
        **kwargs,
    ) -> list[dict]:
        raise ReviewSourceError(self.message)
