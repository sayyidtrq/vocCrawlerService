from __future__ import annotations


class ApifyAllAccountsExhaustedError(RuntimeError):
    """Raised when no configured Apify account remains usable."""


class ApifyTokenPool:
    def __init__(self, tokens: list[str]):
        self._tokens = [token.strip() for token in tokens if token.strip()]
        self._index = 0

    @property
    def current_index(self) -> int:
        return self._index

    def current(self) -> str:
        if self._index >= len(self._tokens):
            raise ApifyAllAccountsExhaustedError(
                "All configured Apify accounts are exhausted."
            )
        return self._tokens[self._index]

    def token_at(self, index: int) -> str:
        """Token akun tertentu - run yang diparkir harus dilanjutkan dengan akun
        yang memulainya."""
        if not 0 <= index < len(self._tokens):
            raise ApifyAllAccountsExhaustedError(
                f"Apify account #{index} is not configured."
            )
        return self._tokens[index]

    def rotate(self) -> str | None:
        self._index += 1
        return self._tokens[self._index] if self._index < len(self._tokens) else None
