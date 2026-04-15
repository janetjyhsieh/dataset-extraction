from __future__ import annotations

import base64
from pathlib import Path

import openai

DEFAULT_MODEL = "gpt-4o"


class OpenAIClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = openai.OpenAI()

    def send_pdf(self, pdf_path: str | Path, prompt: str) -> str:
        """Send a PDF and a text prompt to OpenAI and return the response text.

        Args:
            pdf_path: Path to the PDF file.
            prompt: Instruction to send alongside the PDF.

        Returns:
            Text content of the model's response.
        """
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
