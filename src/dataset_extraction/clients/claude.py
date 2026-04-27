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

    def send_pdf_structured(
        self,
        pdf_path: str | Path,
        prompt: str,
        schema: dict,
    ) -> dict:
        """Send a PDF and prompt to Claude, returning output conforming to *schema*.

        Forces structured output via tool use: Claude is required to call a
        single tool whose input schema is *schema*, guaranteeing the response
        matches the expected JSON structure.

        Args:
            pdf_path: Path to the PDF file.
            prompt: Instruction to send alongside the PDF.
            schema: JSON Schema dict describing the required output structure.

        Returns:
            A dict conforming to *schema*.
        """
        pdf_data = base64.standard_b64encode(Path(pdf_path).read_bytes()).decode("utf-8")

        tool = {
            "name": "extract",
            "description": "Extract structured information from the paper according to the user's instructions.",
            "input_schema": schema,
        }

        with self._client.messages.stream(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            tools=[tool],
            tool_choice={"type": "tool", "name": "extract"},
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

        tool_block = next(b for b in final.content if b.type == "tool_use")
        return tool_block.input
