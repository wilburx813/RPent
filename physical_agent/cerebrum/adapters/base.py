"""Normalised API adapter interface for tool-use model backends."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from physical_agent.utils.logging import get_logger


@dataclass
class ToolCall:
    """Provider-independent tool invocation requested by a model turn."""

    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: Any = None
    parse_error: str | None = None


@dataclass
class ToolResult:
    """Result of executing one normalised tool call."""

    call_id: str
    name: str
    result: dict[str, Any]


@dataclass
class ModelTurn:
    """Provider-independent view of one assistant turn."""

    raw_response: Any
    assistant_payload: Any
    stop_reason: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class ConversationState:
    """Provider-independent mutable conversation state."""

    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    system: Any = None


class ApiAdapter(ABC):
    """Provider-specific bridge used by the shared API agent loop."""

    name: str = ""
    _LOGGER_NAME: str = ""

    def __init__(
        self,
        client: Any,
        model: str,
        max_tokens: int = 4096,
        *,
        thinking: bool = False,
    ):
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._thinking = bool(thinking)
        self._logger = get_logger(self._LOGGER_NAME)

    @abstractmethod
    def start(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools_spec: list[dict[str, Any]],
    ) -> ConversationState:
        """Create provider-specific mutable conversation state."""

    @abstractmethod
    def call(self, state: ConversationState) -> ModelTurn | None:
        """Call the provider and return a normalised assistant turn."""

    @abstractmethod
    def append_assistant(self, state: ConversationState, turn: ModelTurn) -> None:
        """Append the provider-native assistant payload to conversation state."""

    @abstractmethod
    def append_tool_results(
        self,
        state: ConversationState,
        tool_results: list[ToolResult],
        tool_result_formatter: Callable[[dict[str, Any]], list[dict[str, Any]]],
    ) -> None:
        """Append provider-native tool-result messages to conversation state."""

    @abstractmethod
    def log_model_turn(
        self,
        turn: ModelTurn,
        *,
        usage_totals: dict[str, int],
    ) -> None:
        """Emit provider-specific logs for one assistant turn."""

    @abstractmethod
    def _do_call(self, state: ConversationState) -> Any:
        """Issue a single provider-specific API call. Raise on error."""

    def is_normal_stop(self, turn: ModelTurn) -> bool:
        """Return whether a no-tool assistant turn should end the loop."""
        return turn.stop_reason in ("stop", "end_turn", None)

    def messages(self, state: ConversationState) -> list[dict[str, Any]]:
        """Return a serialisable transcript from provider state."""
        return state.messages

    def api_failure_error(self) -> str:
        """Return the error string used when retries are exhausted."""
        return f"{self.name} API call failed after retries"

    def _is_retryable_error(self, error: Exception) -> bool:
        """Return whether an exception from ``_do_call`` should be retried."""
        name = type(error).__name__
        if name in {
            "APIConnectionError",
            "APITimeoutError",
            "InternalServerError",
            "RateLimitError",
            "Timeout",
            "TimeoutException",
            "KeyError",
        }:
            return True
        status_code = getattr(error, "status_code", None)
        return status_code in {408, 409, 429} or (
            isinstance(status_code, int) and status_code >= 500
        )

    def _call_with_retries(self, state: ConversationState) -> Any:
        """Three-attempt retry loop with linear back-off shared across providers."""
        last_err = None
        for attempt in range(3):
            try:
                return self._do_call(state)
            except Exception as e:  # noqa: BLE001 - dispatched to provider hook
                if not self._is_retryable_error(e):
                    raise
                last_err = e
                wait = 10 * (attempt + 1)
                self._logger.warning(
                    "API error '%s: %s' - sleeping %ds (retry %d/3)",
                    type(e).__name__, e, wait, attempt + 1,
                )
                time.sleep(wait)
        self._logger.error("giving up after 3 retries; last error: %s", last_err)
        return None
