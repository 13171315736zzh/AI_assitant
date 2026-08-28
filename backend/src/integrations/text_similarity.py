import re
from difflib import SequenceMatcher


def _normalize(text: str) -> str:
    return re.sub(r"[？?。，,、\s]", "", text.strip().lower())


def _tokens(text: str) -> set[str]:
    normalized = _normalize(text)
    parts = re.findall(r"[\u4e00-\u9fff]+|\w+", normalized)
    chars = {ch for ch in normalized if "\u4e00" <= ch <= "\u9fff"}
    return set(parts) | chars


def _bigrams(text: str) -> set[str]:
    normalized = _normalize(text)
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[i : i + 2] for i in range(len(normalized) - 1)}


def text_similarity(query: str, target: str) -> float:
    query = query.strip()
    target = target.strip()
    if not query or not target:
        return 0.0

    nq, nt = _normalize(query), _normalize(target)
    if nq in nt or nt in nq:
        return max(0.92, SequenceMatcher(None, nq, nt).ratio())

    tq, tt = _tokens(query), _tokens(target)
    jaccard = len(tq & tt) / len(tq | tt) if tq and tt else 0.0
    seq = SequenceMatcher(None, nq, nt).ratio()
    bq, bt = _bigrams(query), _bigrams(target)
    bigram = len(bq & bt) / len(bq | bt) if bq and bt else 0.0
    overlap = len(tq & tt) / len(tq) if tq else 0.0

    score = min(1.0, 0.3 * seq + 0.25 * bigram + 0.25 * jaccard + 0.2 * overlap)
    if overlap >= 0.75:
        score = max(score, 0.85)
    return score
