from __future__ import annotations

import json
from types import SimpleNamespace

from physicalagent.cerebrum.openai_compat import (
    OpenAICompatibleCerebrum,
    _format_tool_result_for_openai,
    anthropic_tools_to_openai_tools,
)


class FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("no fake responses left")
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


TOOLS_SPEC = [
    {
        "name": "finish",
        "description": "Declare the task finished.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["status", "summary"],
        },
    }
]


def _response(*, tool_calls=None, content="", finish_reason="stop"):
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content, tool_calls=tool_calls or []),
            )
        ],
    )


def _tool_call(name: str, arguments: dict):
    return SimpleNamespace(
        id="call_1",
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def test_anthropic_tools_to_openai_tools_converts_schema():
    tools = anthropic_tools_to_openai_tools(TOOLS_SPEC)

    assert tools == [
        {
            "type": "function",
            "function": {
                "name": "finish",
                "description": "Declare the task finished.",
                "parameters": TOOLS_SPEC[0]["input_schema"],
            },
        }
    ]
    assert tools[0]["function"]["parameters"] is not TOOLS_SPEC[0]["input_schema"]


def test_openai_compatible_cerebrum_executes_finish_tool_call():
    tool_call = _tool_call("finish", {"status": "success", "summary": "done"})
    client = FakeClient([_response(tool_calls=[tool_call], finish_reason="tool_calls")])
    cerebrum = OpenAICompatibleCerebrum(client, model="deepseek-v4-pro")

    def tool_handler(name, arguments):
        assert name == "finish"
        assert arguments == {"status": "success", "summary": "done"}
        return {"_finish": True, **arguments}

    result = cerebrum.solve(
        system_prompt="system",
        user_message="user",
        tools_spec=TOOLS_SPEC,
        tool_handler=tool_handler,
        tool_result_formatter=lambda result: [
            {"type": "text", "text": json.dumps(result)}
        ],
        verbose=False,
    )

    assert result.finish_result == {
        "_finish": True,
        "status": "success",
        "summary": "done",
    }
    assert result.stats == {
        "total_input_tokens": 3,
        "total_output_tokens": 2,
        "turns_used": 1,
        "tool_calls": 1,
    }
    assert result.messages[-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": '{"_finish": true, "status": "success", "summary": "done"}',
    }
    assert client.chat.completions.calls[0]["model"] == "deepseek-v4-pro"
    assert client.chat.completions.calls[0]["tool_choice"] == "auto"


def test_format_tool_result_for_openai_splits_text_and_image_blocks():
    text, image_blocks = _format_tool_result_for_openai(
        {"state": "ok"},
        lambda _result: [
            {"type": "text", "text": "state text"},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "abc123",
                },
            },
        ],
        supports_images=True,
        tool_name="view_repl_state",
    )

    assert text == "state text"
    assert image_blocks == [
        {"type": "text", "text": "Image returned by tool view_repl_state."},
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,abc123"},
        },
    ]


def test_format_tool_result_for_openai_can_omit_images():
    text, image_blocks = _format_tool_result_for_openai(
        {"state": "ok"},
        lambda _result: [
            {"type": "text", "text": "state text"},
            {"type": "image", "source": {"type": "base64", "data": "abc123"}},
        ],
        supports_images=False,
        tool_name="view_repl_state",
    )

    assert "state text" in text
    assert "1 image result(s) omitted" in text
    assert image_blocks == []
