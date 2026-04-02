from __future__ import annotations

from pathlib import Path
from typing import Any

import openreview


def download_pdf(
    client: Any,
    note: openreview.Note,
    output_dir: str | Path,
) -> Path:
    """Download the PDF for a single note.

    Args:
        client: An OpenReview API client (v1 or v2).
        note: The note whose PDF to download.
        output_dir: Directory to save the PDF in.

    Returns:
        The :class:`Path` of the saved PDF file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_bytes = client.get_pdf(note.id)
    dest = output_dir / f"{note.id}.pdf"
    dest.write_bytes(pdf_bytes)
    return dest


def download_pdfs(
    client: Any,
    notes: list[openreview.Note],
    output_dir: str | Path,
) -> list[Path]:
    """Download PDFs for a list of notes.

    Args:
        client: An OpenReview API client (v1 or v2).
        notes: Notes whose PDFs to download.
        output_dir: Directory to save PDFs in.

    Returns:
        Paths of successfully saved PDF files.
    """
    n = len(notes)
    paths = []
    for i, note in enumerate(notes, start=1):
        print(f"Downloading {i}/{n}: {note.id}")
        try:
            path = download_pdf(client, note, output_dir)
            paths.append(path)
        except Exception as e:
            print(f"Warning: failed to download {note.id}: {e}")
    return paths
