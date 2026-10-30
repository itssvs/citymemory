"""Rule-based root-cause tagger.

Returns one tag from a fixed list plus the keywords that triggered it, so the reason is
always inspectable. This is the swap point for an LLM tagger: keep the same return shape.
"""
import re

CAUSES = [
    "drainage",
    "utility_digging",
    "heavy_load",
    "poor_patch_material",
    "electrical_fault",
    "wear_and_age",
    "unknown",
]

_KEYWORDS = {
    "drainage": r"water|overflow|waterlogging|stagnant|rain|seep|flood|blocked|sewage|smell",
    "utility_digging": r"dug|digging|trench|cable|pipeline|pipe|utility|excavat|restor",
    "heavy_load": r"truck|lorry|heavy|bus|load|rut",
    "poor_patch_material": r"patch|gravel|cold mix|washed away|came off|did not last|again|same spot|loose",
    "electrical_fault": r"notworking|flicker|fuse|wire|electric|dark|short circuit|sparking|bulb",
    "wear_and_age": r"crack|old|worn|uneven|tile|broken|sinking|slab|cover",
}

_ORDER = ["drainage", "utility_digging", "heavy_load", "poor_patch_material", "electrical_fault", "wear_and_age"]


def tag_cause(clean_text: str, category: str):
    """clean_text must already be normalised (see textsim.normalise)."""
    text = clean_text or ""
    for cause in _ORDER:
        if cause == "electrical_fault" and category != "streetlight":
            continue
        pattern = _KEYWORDS[cause]
        if cause == "drainage" and category != "drain":
            pattern = pattern + r"|drain"  # for a road/footpath, a nearby drain is a cause
        hits = sorted(set(re.findall(pattern, text)))
        if hits:
            return cause, "matched: " + ", ".join(hits)
    return "unknown", "no cause keywords found"


def severity_from_text(clean_text: str) -> int:
    t = clean_text or ""
    if re.search(r"accident|injur|fell|fall|dangerous|deep|flood|sparking|exposed|skid|bleed", t):
        return 4
    if re.search(r"minor|small|slight", t):
        return 2
    return 3
