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
        thinking: bool = False,
    ) -> tuple[str | None, dict]:
        """Send a PDF and prompt to Claude, returning structured output.

        Args:
            pdf_path: Path to the PDF file.
            prompt: Instruction to send alongside the PDF.
            schema: JSON Schema dict describing the required output structure.
            thinking: If True, enable extended thinking and return the
                reasoning text as the first element of the tuple.

        Returns:
            A ``(thinking_text, result)`` tuple. *thinking_text* is the model's
            reasoning if *thinking* is True, otherwise None.
        """
        pdf_data = base64.standard_b64encode(Path(pdf_path).read_bytes()).decode("utf-8")

        tool = {
            "name": "extract",
            "description": "Extract structured information from the paper according to the user's instructions.",
            "input_schema": schema,
        }

        thinking_param = (
            {"type": "enabled", "budget_tokens": 10000} if thinking
            else {"type": "disabled"}
        )

        with self._client.messages.stream(
            model=self.model,
            max_tokens=16000,
            thinking=thinking_param,
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

        thinking_text = (
            "\n\n".join(b.thinking for b in final.content if b.type == "thinking") or None
            if thinking else None
        )
        tool_block = next(b for b in final.content if b.type == "tool_use")
        return thinking_text, tool_block.input
