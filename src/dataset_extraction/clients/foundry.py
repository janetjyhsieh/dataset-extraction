from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from dataset_extraction.clients.openai import _make_strict

DEFAULT_MODEL = "gpt-5.4-nano"


class FoundryClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
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

    def send_pdf(self, pdf_path: str | Path, prompt: str) -> str:
        response = self._client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": self._pdf_content(pdf_path, prompt)}],
        )
        return response.output_text

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
