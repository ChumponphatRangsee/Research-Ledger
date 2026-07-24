"""Provider-agnostic market data failures."""


class MarketDataProviderError(Exception):
    """Base error raised while retrieving or normalizing market data."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        symbol: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.symbol = symbol


class ProviderUnavailableError(MarketDataProviderError):
    """The provider is temporarily unavailable."""


class ProviderTimeoutError(ProviderUnavailableError):
    """The provider did not respond before the request deadline."""


class ProviderRateLimitError(ProviderUnavailableError):
    """The provider rejected a request because its rate limit was reached."""


class SymbolNotFoundError(MarketDataProviderError):
    """The requested symbol is unknown to the provider."""


class InvalidProviderResponseError(MarketDataProviderError):
    """The provider returned data that cannot form a normalized snapshot."""
