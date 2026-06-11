import json
from pathlib import Path


def load_title_map(working_dir: Path) -> dict[str, str]:
    index_path = working_dir / "index.jsonl"
    if not index_path.exists():
        return {}
    title_map: dict[str, str] = {}
    with open(index_path) as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                title_map[record["id"]] = record["title"]
    return title_map
