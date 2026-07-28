import re

def titles_match(query: str, result: str, threshold: float = 0.9) -> bool:
    norm_q = re.sub(r"[^a-z0-9 ]", "", query.lower())
    norm_r = re.sub(r"[^a-z0-9 ]", "", result.lower())
    return norm_q == norm_r