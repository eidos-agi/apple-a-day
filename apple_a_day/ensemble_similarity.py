"""Ensemble app similarity scoring.

Six independent voters, each covering different blind spots:
  1. Synonym groups — known pairs (high precision, zero discovery)
  2. Brew descriptions — text similarity on developer descriptions
  3. Localization vocabulary — UI word overlap (native apps only)
  4. Category + UTIs — Apple's metadata (medium noise)
  5. Runtime + frameworks — build similarity (weak for purpose)
  6. Replacement detection — temporal usage patterns

Each voter returns (score: 0-1, weight: float, reason: str | None).
Weight is 0 when the voter has no signal (missing data).
Final score = weighted average of voters that have signal.
"""

import math


def ensemble_score(meta_a: dict, meta_b: dict) -> tuple[float, list[str]]:
    """Score similarity between two apps using all available signals.

    Returns (score: 0-1, reasons: list of explanations).
    """
    votes: list[tuple[float, float, str]] = []  # (score, weight, reason)

    # 1. Brew descriptions — text similarity on what the developer says it does
    desc_a = meta_a.get("brew_desc", "")
    desc_b = meta_b.get("brew_desc", "")
    if desc_a and desc_b:
        sim = _text_cosine(desc_a, desc_b)
        if sim > 0.1:
            votes.append((sim, 2.5, f"similar descriptions ({sim:.0%})"))

    # 3. Localization vocabulary — UI word overlap
    vocab_a = meta_a.get("ui_vocabulary", set())
    vocab_b = meta_b.get("ui_vocabulary", set())
    if vocab_a and vocab_b:
        jaccard = _jaccard(vocab_a, vocab_b)
        if jaccard > 0.05:
            votes.append(
                (
                    min(jaccard * 4, 1.0),
                    2.0,
                    f"shared UI vocabulary ({len(vocab_a & vocab_b)} words)",
                )
            )

    # 4. Category + UTIs
    cat_score = _category_signal(meta_a, meta_b)
    if cat_score > 0:
        cat_label = meta_a.get("category", "").replace("public.app-category.", "").replace("-", " ")
        votes.append((cat_score, 1.5, f"both in '{cat_label}' category"))

    uti_score = _uti_signal(meta_a, meta_b)
    if uti_score > 0:
        votes.append((uti_score, 1.5, "shared file types"))

    # 5. Runtime + frameworks (supporting evidence only — weak for purpose)
    rt_a = meta_a.get("runtime", "unknown")
    rt_b = meta_b.get("runtime", "unknown")
    if rt_a == rt_b and rt_a not in ("unknown", "native"):
        votes.append((0.3, 0.3, f"both {rt_a} apps"))

    fw_a = meta_a.get("frameworks", set())
    fw_b = meta_b.get("frameworks", set())
    fw_jaccard = _jaccard(fw_a, fw_b)
    if fw_jaccard > 0.2:
        votes.append((fw_jaccard, 0.3, "shared frameworks"))

    # 6. URL scheme overlap
    urls_a = meta_a.get("url_schemes", set())
    urls_b = meta_b.get("url_schemes", set())
    generic_schemes = {"http", "https", "file", "mailto"}
    specific_overlap = (urls_a - generic_schemes) & (urls_b - generic_schemes)
    if specific_overlap:
        votes.append((0.6, 1.0, f"shared URL schemes: {', '.join(sorted(specific_overlap)[:3])}"))

    # 7. Same vendor (supporting signal only)
    vendor_a = meta_a.get("vendor", "")
    vendor_b = meta_b.get("vendor", "")
    if vendor_a and vendor_b and vendor_a == vendor_b and vendor_a not in ("com.apple",):
        votes.append((0.3, 0.5, f"same developer ({vendor_a})"))

    # Aggregate: weighted average of all voters that had signal
    if not votes:
        return 0.0, []

    total_weight = sum(w for _, w, _ in votes)
    weighted_sum = sum(s * w for s, w, _ in votes)
    score = weighted_sum / total_weight

    # Consensus bonus: if 3+ voters agree (score > 0.3), boost confidence
    agreeing = sum(1 for s, _, _ in votes if s > 0.3)
    if agreeing >= 3:
        score = min(1.0, score * 1.15)

    reasons = [r for _, _, r in votes if r]
    return round(score, 3), reasons


def _text_cosine(text_a: str, text_b: str) -> float:
    """Cosine similarity on word bags, with concept expansion.

    Expands words to include semantic neighbors so that
    "messaging" and "communication" match, "editor" and "IDE" match, etc.
    """
    words_a = _expand_concepts(_tokenize(text_a))
    words_b = _expand_concepts(_tokenize(text_b))
    if not words_a or not words_b:
        return 0.0

    all_words = words_a | words_b
    vec_a = [1 if w in words_a else 0 for w in all_words]
    vec_b = [1 if w in words_b else 0 for w in all_words]

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# Concept groups: words within a group are treated as equivalent
_CONCEPT_GROUPS = [
    {"messaging", "communication", "chat", "messenger", "conversations"},
    {"editor", "ide", "coding", "code", "programming", "development"},
    {"browser", "web", "browsing", "internet"},
    {"spreadsheet", "worksheet", "tabular", "excel"},
    {"presentation", "slides", "slideshow"},
    {"document", "writing", "word", "processor", "text"},
    {"recording", "recorder", "capture", "screen"},
    {"video", "streaming", "media", "player"},
    {"database", "sql", "query", "data"},
    {"remote", "desktop", "access", "rdp", "vnc"},
    {"storage", "cloud", "sync", "drive", "backup"},
    {"virtual", "machine", "virtualization", "vm", "container"},
    {"password", "credential", "vault", "keychain"},
    {"meeting", "conferencing", "call", "video"},
    {"notes", "notebook", "note-taking"},
    {"design", "graphics", "illustration", "drawing"},
    {"photo", "image", "editing", "photography"},
    {"terminal", "shell", "console", "command"},
    {"git", "version", "control", "repository"},
    {"email", "mail", "inbox"},
]


def _expand_concepts(words: set[str]) -> set[str]:
    """Expand a word set with semantic neighbors from concept groups."""
    expanded = set(words)
    for word in words:
        for group in _CONCEPT_GROUPS:
            if word in group:
                expanded |= group
    return expanded


_STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "for",
    "of",
    "in",
    "on",
    "to",
    "with",
    "is",
    "it",
    "by",
    "as",
    "at",
    "from",
    "that",
    "this",
    "your",
    "app",
    "native",
    "client",
    "official",
    "desktop",
    "tool",
    "software",
    "application",
    "just",
    "one",
    "place",
    "focus",
}


def _tokenize(text: str) -> set[str]:
    """Tokenize text into meaningful lowercase words."""
    return {
        w.lower()
        for w in text.split()
        if len(w) > 2 and w.lower() not in _STOP_WORDS and w.isalpha()
    }


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _category_signal(meta_a: dict, meta_b: dict) -> float:
    cat_a = meta_a.get("category", "")
    cat_b = meta_b.get("category", "")
    if not cat_a or not cat_b or cat_a != cat_b:
        return 0.0
    # These categories are too broad to mean much alone
    broad = {
        "public.app-category.utilities",
        "public.app-category.productivity",
        "public.app-category.business",
        "public.app-category.developer-tools",  # Claude and Cursor are both here
        "public.app-category.entertainment",
        "public.app-category.lifestyle",
    }
    return 0.2 if cat_a in broad else 0.7


def _uti_signal(meta_a: dict, meta_b: dict) -> float:
    utis_a = meta_a.get("utis", set())
    utis_b = meta_b.get("utis", set())
    generic = {
        "public.data",
        "public.item",
        "public.content",
        "public.text",
        "public.plain-text",
        "public.image",
        "public.movie",
        "public.composite-content",
    }
    a = utis_a - generic
    b = utis_b - generic
    return _jaccard(a, b)
