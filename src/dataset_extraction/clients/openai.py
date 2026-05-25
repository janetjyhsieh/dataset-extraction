from __future__ import annotations

import base64
import json
from pathlib import Path

import openai

DEFAULT_MODEL = "gpt-5"


def _make_strict(schema: dict) -> dict:
    schema = {k: v for k, v in schema.items() if k != "default"}

    if schema.get("type") == "object" or "properties" in schema:
        schema["additionalProperties"] = False
        if "properties" in schema:
            schema["required"] = list(schema["properties"].keys())
            schema["properties"] = {
                k: _make_strict(v) for k, v in schema["properties"].items()
            }

    if "$defs" in schema:
        schema["$defs"] = {k: _make_strict(v) for k, v in schema["$defs"].items()}
    if "items" in schema:
        schema["items"] = _make_strict(schema["items"])
    for key in ("anyOf", "allOf", "oneOf"):
        if key in schema:
            schema[key] = [_make_strict(s) for s in schema[key]]

    return schema


class OpenAIClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = openai.OpenAI()

    def send_pdf(self, pdf_path: str | Path, prompt: str) -> str:
        pdf_data = base64.standard_b64encode(Path(pdf_path).read_bytes()).decode("utf-8")
        filename = Path(pdf_path).name

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "filename": filename,
                            "file_data": f"data:application/pdf;base64,{pdf_data}",
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return response.choices[0].message.content

    def send_pdf_structured(
        self,
        pdf_path: str | Path,
        prompt: str,
        schema: dict,
        thinking: bool = False,
    ) -> tuple[None, dict]:
        pdf_data = base64.standard_b64encode(Path(pdf_path).read_bytes()).decode("utf-8")
        filename = Path(pdf_path).name
        schema_name = schema.get("title", "output")

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "filename": filename,
                            "file_data": f"data:application/pdf;base64,{pdf_data}",
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": _make_strict(schema),
                    "strict": True,
                },
            },
        )
        return None, json.loads(response.choices[0].message.content)
