"""OpenAI-compatible chat-completions cerebrum with tool calling.

This backend targets providers that expose the OpenAI Chat Completions wire
protocol, including OpenAI itself and compatible hosted model endpoints.
"""
from __future__ import annotations

import copy
import json
import time
from typing import Any, Callable

from physicalagent.cerebrum.base import CerebrumResult


class OpenAICompatibleCerebrum:
    """Cerebrum backed by an OpenAI-compatible Chat Completions client."""

    def __init__(
        self,
        client: Any,
        model: str,
        max_tokens: int = 4096,
        *,
        supports_images: bool = True,
    ):
        """Create a backend around a pre-configured OpenAI SDK client."""
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._supports_images = supports_images

    # ------------------------------------------------------------------
    # Cerebrum protocol
    # ------------------------------------------------------------------

    def solve(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools_spec: list[dict[str, Any]],
        tool_handler: Callable[[str, dict[str, Any]], dict[str, Any]],
        tool_result_formatter: Callable[[dict[str, Any]], list[dict[str, Any]]],
        max_turns: int = 80,
        verbose: bool = True,
    ) -> CerebrumResult:
        """Run a tool-calling chat-completions loop until finish or budget."""
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        finish_result = None
        total_in = total_out = 0
        n_tool_calls = 0
        last_error = None
        turn = 0
        tools = anthropic_tools_to_openai_tools(tools_spec)

        for turn in range(1, max_turns + 1):
            if verbose:
                print(f"\n[agent] === turn {turn}/{max_turns} ===")

            response = self._call_with_retries(
                tools=tools,
                messages=messages,
                verbose=verbose,
            )
            if response is None:
                last_error = "OpenAI-compatible API call failed after retries"
                break

            usage = _get(response, "usage")
            input_tokens = int(_get(usage, "prompt_tokens", 0) or 0)
            output_tokens = int(_get(usage, "completion_tokens", 0) or 0)
            total_in += input_tokens
            total_out += output_tokens

            choice = _first_choice(response)
            message = _get(choice, "message")
            finish_reason = _get(choice, "finish_reason")
            assistant_message = _assistant_message_to_dict(message)

            if verbose:
                self._log_response(
                    assistant_message,
                    finish_reason,
                    input_tokens,
                    output_tokens,
                    total_in,
                    total_out,
                )

            messages.append(assistant_message)
            tool_calls = assistant_message.get("tool_calls") or []

            if tool_calls:
                tool_messages, image_messages, finish_result, n = self._execute_tools(
                    tool_calls,
                    tool_handler,
                    tool_result_formatter,
                    verbose,
                )
                n_tool_calls += n
                messages.extend(tool_messages)
                messages.extend(image_messages)
                if finish_result is not None:
                    if verbose:
                        print(f"\n[agent] FINISH called: {finish_result}")
                    break
            elif finish_reason in ("stop", "end_turn", None):
                if verbose:
                    print("[agent] model ended turn without a tool call. Stopping.")
                break
            else:
                if verbose:
                    print(f"[agent] unexpected finish_reason: {finish_reason}")
                break

        return CerebrumResult(
            finish_result=finish_result,
            messages=messages,
            stats={
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "turns_used": turn,
                "tool_calls": n_tool_calls,
            },
            error=last_error,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_with_retries(
        self,
        *,
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        verbose: bool,
    ):
        last_err = None
        for outer in range(3):
            try:
                return self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    max_tokens=self._max_tokens,
                )
            except Exception as e:  # noqa: BLE001 - SDK-compatible errors vary by provider.
                last_err = e
                if not _is_retryable_error(e):
                    if verbose:
                        print(
                            f"[agent] non-retryable API error "
                            f"'{type(e).__name__}: {e}'"
                        )
                    raise
                wait = 10 * (outer + 1)
                if verbose:
                    print(
                        f"[agent] API error '{type(e).__name__}: {e}' "
                        f"- sleeping {wait}s (retry {outer + 1}/3)"
                    )
                time.sleep(wait)
        if verbose:
            print(f"[agent] giving up after 3 retries; last error: {last_err}")
        return None

    @staticmethod
    def _log_response(
        assistant_message: dict[str, Any],
        finish_reason: str | None,
        input_tokens: int,
        output_tokens: int,
        total_in: int,
        total_out: int,
    ) -> None:
        content = assistant_message.get("content")
        if isinstance(content, str) and content.strip():
            print(f"[openai] {content.strip()}")
        for tool_call in assistant_message.get("tool_calls") or []:
            function = tool_call.get("function") or {}
            name = function.get("name", "?")
            arguments = function.get("arguments") or "{}"
            if len(arguments) > 250:
                arguments = arguments[:250] + "...(+%d)" % (len(arguments) - 250)
            print(f"[tool->] {name}({arguments})")
        print(
            f"[usage] in={input_tokens}  out={output_tokens}  "
            f"stop={finish_reason}  total_in={total_in}  total_out={total_out}"
        )

    def _execute_tools(
        self,
        tool_calls: list[dict[str, Any]],
        tool_handler: Callable,
        tool_result_formatter: Callable,
        verbose: bool,
    ):
        tool_messages = []
        image_blocks = []
        finish_result = None
        n = 0
        for tool_call in tool_calls:
            n += 1
            call_id = tool_call.get("id") or f"tool_call_{n}"
            function = tool_call.get("function") or {}
            name = function.get("name", "")
            raw_arguments = function.get("arguments") or "{}"
            arguments, parse_error = _parse_tool_arguments(raw_arguments)
            if parse_error is not None:
                result = {"error": parse_error, "raw_arguments": raw_arguments}
            else:
                result = tool_handler(name, arguments)

            if isinstance(result, dict) and result.get("_finish"):
                finish_result = result

            if verbose:
                summary = _summarise_result(result)
                s = json.dumps(summary, default=str)
                if len(s) > 350:
                    s = s[:350] + "...(+%d)" % (len(s) - 350)
                print(f"[tool<-] {name}: {s}")

            tool_text, tool_image_blocks = _format_tool_result_for_openai(
                result,
                tool_result_formatter,
                supports_images=self._supports_images,
                tool_name=name,
            )
            tool_messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": tool_text,
            })
            image_blocks.extend(tool_image_blocks)

        image_messages = []
        if image_blocks:
            image_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Images returned by the preceding tool calls.",
                    },
                    *image_blocks,
                ],
            })
        return tool_messages, image_messages, finish_result, n


def anthropic_tools_to_openai_tools(
    tools_spec: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert Anthropic-style tool definitions to OpenAI function tools."""
    tools = []
    for tool in tools_spec:
        tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": copy.deepcopy(tool.get("input_schema") or {}),
            },
        })
    return tools


def _format_tool_result_for_openai(
    result: dict[str, Any],
    tool_result_formatter: Callable[[dict[str, Any]], list[dict[str, Any]]],
    *,
    supports_images: bool,
    tool_name: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Convert Anthropic content blocks into OpenAI tool/user messages."""
    formatter_input = copy.deepcopy(result) if isinstance(result, dict) else result
    blocks = tool_result_formatter(formatter_input)
    text_parts: list[str] = []
    image_blocks: list[dict[str, Any]] = []
    omitted_images = 0

    for block in blocks:
        block_type = _get(block, "type")
        if block_type == "text":
            text = _get(block, "text", "")
            if text:
                text_parts.append(str(text))
        elif block_type == "image":
            image_url = _image_block_to_url(block)
            if supports_images and image_url:
                image_blocks.extend([
                    {
                        "type": "text",
                        "text": f"Image returned by tool {tool_name}.",
                    },
                    {"type": "image_url", "image_url": {"url": image_url}},
                ])
            else:
                omitted_images += 1
        else:
            text_parts.append(json.dumps(_to_plain_data(block), default=str))

    if omitted_images:
        text_parts.append(
            f"[{omitted_images} image result(s) omitted because this "
            "OpenAI-compatible backend is configured without image support.]"
        )

    text = "\n\n".join(part for part in text_parts if part)
    if not text:
        text = "{}"
    return text, image_blocks


def _image_block_to_url(block: Any) -> str | None:
    source = _get(block, "source") or {}
    source_type = _get(source, "type")
    if source_type == "base64":
        media_type = _get(source, "media_type", "image/png")
        data = _get(source, "data")
        if data:
            return f"data:{media_type};base64,{data}"
    url = _get(source, "url")
    return str(url) if url else None


def _assistant_message_to_dict(message: Any) -> dict[str, Any]:
    content = _get(message, "content")
    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": content if content is not None else "",
    }
    tool_calls = _get(message, "tool_calls") or []
    if tool_calls:
        assistant_message["tool_calls"] = [
            _tool_call_to_dict(tool_call) for tool_call in tool_calls
        ]
    return assistant_message


def _tool_call_to_dict(tool_call: Any) -> dict[str, Any]:
    function = _get(tool_call, "function") or {}
    return {
        "id": _get(tool_call, "id"),
        "type": _get(tool_call, "type", "function"),
        "function": {
            "name": _get(function, "name"),
            "arguments": _get(function, "arguments", "{}"),
        },
    }


def _parse_tool_arguments(raw_arguments: Any) -> tuple[dict[str, Any], str | None]:
    if isinstance(raw_arguments, dict):
        return raw_arguments, None
    if raw_arguments in (None, ""):
        return {}, None
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as e:
        return {}, f"invalid JSON tool arguments: {e}"
    if not isinstance(parsed, dict):
        error = f"tool arguments must decode to an object, got {type(parsed).__name__}"
        return {}, error
    return parsed, None


def _first_choice(response: Any) -> Any:
    choices = _get(response, "choices") or []
    if not choices:
        raise RuntimeError("OpenAI-compatible response did not include choices")
    return choices[0]


def _is_retryable_error(error: Exception) -> bool:
    name = type(error).__name__
    if name in {
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "RateLimitError",
        "Timeout",
        "TimeoutException",
    }:
        return True
    status_code = getattr(error, "status_code", None)
    return status_code in {408, 409, 429} or (
        isinstance(status_code, int) and status_code >= 500
    )


def _summarise_result(result: dict) -> dict:
    """Strip large fields from a tool result for console display."""
    if not isinstance(result, dict):
        return {"result": str(result)}
    summary = {
        k: v
        for k, v in result.items()
        if k not in ("state", "content", "log", "_image_path", "_image_cam_path")
    }
    if "state" in result:
        state = result["state"]
        summary["state_summary"] = {
            "eef": [round(x, 3) for x in state.get("robot0_eef_pos", [])][:3],
            "libero_terminated": result.get("libero_terminated"),
        }
    if "log" in result:
        log = result["log"]
        if isinstance(log, dict) and "result" in log:
            summary["log_result_keys"] = list(log["result"].keys())
    return summary


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_plain_data(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _to_plain_data(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_plain_data(v) for v in obj]
    if isinstance(obj, tuple):
        return [_to_plain_data(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj
