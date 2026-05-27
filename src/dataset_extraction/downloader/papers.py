from __future__ import annotations

import logging
from typing import Any

import openreview

logger = logging.getLogger(__name__)


def _get_keywords(note: openreview.Note) -> list[str]:
    raw = note.content.get("keywords", [])
    if isinstance(raw, dict):
        # v2 API wraps content fields: {"value": [...]}
        return raw.get("value", [])
    if isinstance(raw, list):
        # v1 API returns the list directly
        return raw
    return []


def _note_matches(note: openreview.Note, keywords: list[str]) -> bool:
    note_keywords = _get_keywords(note) + [note.content.get("title", "")]
    query_lower = [q.lower() for q in keywords]
    or_result =  any(
        any(q in kw.lower() for q in query_lower)
        for kw in note_keywords
        if isinstance(kw, str)
    )
    return or_result


def get_notes(
    client: Any,
    venue: str,
    keywords: list[str],
) -> list[openreview.Note]:
    """Return all notes at `venue` whose keywords match any of `keywords`.

    Args:
        client: An OpenReview API client (v1 ``openreview.Client`` or v2
            ``openreview.api.OpenReviewClient``).
        venue: The venue ID, e.g. ``'NeurIPS.cc/2023/Conference'``. All
            accepted papers whose ``venueid`` content field matches are
            returned, covering orals, spotlights, and posters.
        keywords: Keywords to filter by. A note is included if any of its
            keywords contains any query keyword as a case-insensitive
            substring. If empty, all notes for the venue are returned.

    Returns:
        A list of :class:`openreview.Note` objects matching the criteria.
    """
    notes = client.get_all_notes(content={"venueid": venue})

    if not keywords:
        logger.debug("No keywords filter — returning all notes")
        return notes

    return [note for note in notes if _note_matches(note, keywords)]
