from __future__ import annotations

import base64
from pathlib import Path

import anthropic

DEFAULT_MODEL = "claude-opus-4-6"

# TODO: abstract the cleints to be "LLMClient", and have Claude and Openai be different types of LLMClient
class ClaudeClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = anthropic.Anthropic()

    def send_pdf(self, pdf_path: str | Path, prompt: str) -> str:
        """Send a PDF and a text prompt to Claude and return the response text.

        Uses streaming to avoid timeouts on large PDFs, and adaptive thinking
        for best reasoning quality.

        Args:
            pdf_path: Path to the PDF file.
            prompt: Instruction to send alongside the PDF.

        Returns:
            Text content of Claude's response.
        """
        pdf_data = base64.standard_b64encode(Path(pdf_path).read_bytes()).decode("utf-8")

        with self._client.messages.stream(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        ) as stream:
            final = stream.get_final_message()

        return next(b.text for b in final.content if b.type == "text")
