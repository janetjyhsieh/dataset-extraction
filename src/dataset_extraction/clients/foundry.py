from __future__ import annotations

import base64
import json
import os
import random
import time
from pathlib import Path
from typing import Any, Callable

import openai
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from dataset_extraction.clients.openai import _make_strict

DEFAULT_MODEL = "gpt-5.4-nano"


class FoundryClient:
    def __init__(self, model: str = DEFAULT_MODEL, reasoning_effort: str | None = None):
        self.model = model
        self.reasoning_effort = reasoning_effort
        project_client = AIProjectClient(
            endpoint=os.environ["AZURE_FOUNDRY_ENDPOINT"],
            credential=DefaultAzureCredential(),
        )
        self._client = project_client.get_openai_client()

    def _pdf_content(self, pdf_path: str | Path, prompt: str) -> list[dict]:
        pdf_data = base64.standard_b64encode(Path(pdf_path).read_bytes()).decode("utf-8")
        filename = Path(pdf_path).name
        return [
            {
                "type": "input_file",
                "filename": filename,
                "file_data": f"data:application/pdf;base64,{pdf_data}",
            },
            {"type": "input_text", "text": prompt},
        ]

    def _reasoning_kwargs(self) -> dict:
        if self.reasoning_effort is None:
            return {}
        return {"reasoning": {"effort": self.reasoning_effort}}

    def send_pdf(self, pdf_path: str | Path, prompt: str) -> str:
        response = self._client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": self._pdf_content(pdf_path, prompt)}],
            **self._reasoning_kwargs(),
        )
        return response.output_text

    def send_text_structured(
        self,
        prompt: str,
        schema: dict,
        previous_response_id: str | None = None,
    ) -> tuple[dict, str]:
        schema_name = schema.get("title", "output")
        kwargs: dict = {
            "model": self.model,
            "input": [{"role": "user", "content": prompt}],
            **self._reasoning_kwargs(),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": _make_strict(schema),
                    "strict": True,
                }
            },
        }
        if previous_response_id is not None:
            kwargs["previous_response_id"] = previous_response_id
        response = self._client.responses.create(**kwargs)
        return json.loads(response.output_text), response.id

    def send_pdf_structured(
        self,
        pdf_path: str | Path,
        prompt: str,
        schema: dict,
        thinking: bool = False,
    ) -> tuple[None, dict]:
        schema_name = schema.get("title", "output")
        response = self._client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": self._pdf_content(pdf_path, prompt)}],
            **self._reasoning_kwargs(),
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": _make_strict(schema),
                    "strict": True,
                }
            },
        )
        return None, json.loads(response.output_text)

    def _create_with_backoff(self, max_retries: int = 5, base_delay: float = 1.0, **kwargs) -> Any:
        for attempt in range(max_retries):
            try:
                return self._client.responses.create(**kwargs)
            except openai.RateLimitError:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)

    def run_agent(
        self,
        prompt: str,
        tools: list[dict],
        tool_handlers: dict[str, Callable[[dict], str]],
        output_schema: dict,
        max_tool_calls: int = 20,
    ) -> Any:
        """Run an agentic loop until the model calls `extract_result`.

        The model may call any tool in *tools* any number of times. Once it is
        satisfied, it calls the implicit `extract_result` tool whose schema is
        derived from *output_schema*. That call's arguments are returned as a
        plain dict for the caller to validate.

        Returns:
            The parsed arguments dict from the model's `extract_result` call.

        Raises:
            RuntimeError: If the agent exceeds *max_tool_calls* without finishing.
        """
        extract_tool = {
            "type": "function",
            "name": "extract_result",
            "description": (
                "Output the final structured result once you have gathered all "
                "available information from the landing page."
            ),
            "parameters": _make_strict(output_schema),
            "strict": True,
        }
        all_tools = tools + [extract_tool]

        response = self._create_with_backoff(
            model=self.model,
            input=[{"role": "user", "content": prompt}],
            tools=all_tools,
        )

        for _ in range(max_tool_calls):
            tool_calls = [item for item in response.output if item.type == "function_call"]

            if not tool_calls:
                text = response.output_text
                if not text:
                    raise RuntimeError("Agent returned empty response without calling any tool")
                return json.loads(text)

            results = []
            for call in tool_calls:
                args = json.loads(call.arguments)
                if call.name == "extract_result":
                    return args
                handler = tool_handlers.get(call.name)
                result = handler(args) if handler else f"Unknown tool: {call.name}"
                results.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": result,
                })

            response = self._create_with_backoff(
                model=self.model,
                previous_response_id=response.id,
                input=results,
                tools=all_tools,
            )

        raise RuntimeError(f"Agent exceeded {max_tool_calls} tool calls without finishing.")
