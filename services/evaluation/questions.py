"""Deterministic practitioner-style questions derived from source propositions."""

import re


def _topic(document: dict, section: dict) -> str:
    title = str(document.get("title") or "Untitled")
    substantive = title.split(" - ", 1)[-1].strip() if " - " in title else title
    substantive = substantive.split(": ", 1)[-1].strip() if ": " in substantive else substantive
    heading = str((section.get("heading_path") or [section.get("heading") or title])[-1])
    heading = " ".join(heading.split()).strip(" .")
    heading = re.sub(r"^(?:\d+(?:[-.]\d+)*|[A-Z]|Appendix\s+\d+\.)\s+", "", heading).strip()
    reference = str(document.get("canonical_reference_id") or "").casefold()
    clean = re.sub(r"^(?:taxation\s+ruling|taxation\s+determination|miscellaneous\s+taxation\s+ruling|class\s+ruling|product\s+ruling)\s+", "", heading, flags=re.I).casefold()
    return substantive if not heading or clean == reference else heading


def _leading_condition(sentence: str) -> str | None:
    if not sentence.casefold().startswith("if "):
        return None
    depth = 0
    for index, character in enumerate(sentence[3:], 3):
        depth += character == "("
        depth = max(0, depth - (character == ")"))
        if character == "," and depth == 0:
            value = sentence[3:index].strip().rstrip("?")
            words = re.findall(r"[A-Za-z]{3,}", value)
            return value if len(words) >= 5 and not value.casefold().startswith("during ") else None
    return None


def realistic_question(document: dict, section: dict, passage: str) -> str:
    classification = document.get("classification") or {}
    source_class = classification.get("source_class")
    title = str(document.get("title") or "Untitled").rstrip("?")
    reference = str(document.get("canonical_reference_id") or title)
    topic = _topic(document, section)
    templated_topic = topic.rstrip("?").rstrip()
    first = re.split(r"(?<=[.!?])\s+", " ".join(passage.split()), maxsplit=1)[0]
    lower = first.casefold()
    condition = _leading_condition(first)
    if re.match(r"^(?:what|when|who|how|which|why|are|does|did|can)\b", topic, re.I):
        if topic.casefold().startswith("how to "):
            return f"How should a taxpayer {topic[7:].rstrip('?')}?"
        if topic.casefold().startswith("when to "):
            return f"When should a taxpayer {topic[8:].rstrip('?')}?"
        if topic.casefold().startswith("when the ") and " can " in topic.casefold():
            subject, predicate = re.split(r"\s+can\s+", topic[5:].rstrip("?"), maxsplit=1)
            return f"When can {subject} {predicate}?"
        if topic.casefold().startswith("how ") and not topic.casefold().startswith("how does "):
            return f"How does {topic[4:].rstrip('?')}?"
        return topic if topic.endswith("?") else f"{topic}?"
    if topic.casefold().startswith("if "):
        return f"What is the tax treatment {templated_topic}?"
    if "method statement" in passage.casefold():
        return f"How is {templated_topic} calculated under {reference}?"
    if " means " in lower:
        subject = re.split(r"\s+means\s+", first, maxsplit=1, flags=re.I)[0].strip(" :")
        return f"What does {subject} mean under {reference}?"
    if condition:
        return f"What is the tax treatment when {condition}?"
    if "does not apply" in lower or "excluded" in lower or "exempt" in lower:
        return f"Which entities or transactions are excluded from {templated_topic} under {reference}?"
    if passage.lstrip().startswith("-"):
        return f"What information is required for {templated_topic}?"
    if source_class == "practical_compliance_guideline":
        return f"How does the Commissioner assess compliance risk for {templated_topic} under {reference}?"
    if source_class in {"public_ruling", "taxation_determination", "law_companion_ruling"}:
        topic_clean = re.sub(rf"^(?:taxation\s+ruling|taxation\s+determination|miscellaneous\s+taxation\s+ruling|class\s+ruling|product\s+ruling)?\s*{re.escape(reference)}\s*[-:–]?\s*", "", templated_topic, flags=re.I).strip()
        subject = topic_clean if len(topic_clean) >= 5 else templated_topic
        return f"What does {reference} conclude about {subject}?"
    if source_class == "court_decision":
        case_name = title.replace(reference, "").strip(" -/()") or title
        return f"What issue did the High Court address in {case_name} ({reference})?"
    if " must " in f" {lower} ":
        return f"What requirements apply to {templated_topic} under {reference}?"
    if source_class in {"commonwealth_statute", "commonwealth_regulation"}:
        if re.search(r"\b(?:amount|rate|component|cost base|assessable|taxable|deduction|offset)\b",
                     topic, re.I):
            return f"How does {reference} determine {templated_topic}?"
        if re.search(r"\b(?:offence|penalty|liability)\b", topic, re.I):
            return f"What conduct or liability does {reference} establish for {templated_topic}?"
        if re.search(r"\b(?:application|applies|applying)\b", topic, re.I):
            return f"When does {reference} apply to {templated_topic}?"
        if re.search(r"\b(?:choice|election)\b", topic, re.I):
            return f"What choice is available under {reference} for {templated_topic}?"
        return f"What rule does {reference} establish for {templated_topic}?"
    if re.search(r"\b(?:may|can)\b", lower):
        return f"When may a taxpayer apply the rule concerning {templated_topic}?"
    if " begins " in f" {lower} " and (" ends " in f" {lower} " or "continues" in lower):
        return f"When does {templated_topic} begin and end?"
    if " includes " in f" {lower} ":
        return f"What does {templated_topic} include?"
    if re.search(r"\b(?:return|lodge|lodgment|schedule|form)\b", topic, re.I):
        return f"What are the lodgment requirements for {templated_topic}?"
    if re.search(r"\b(?:income|deduction|offset|capital gain|loss|tax)\b", topic, re.I):
        return f"How is {templated_topic} treated for tax purposes?"
    if "data-matching" in topic.casefold():
        return f"What information does the ATO use for {templated_topic}?"
    return f"What ATO guidance applies to {templated_topic}?"


def question_is_sane(question: str) -> bool:
    value = " ".join(question.split())
    if not 25 <= len(value) <= 260 or not value.endswith("?") or "??" in value:
        return False
    blocked = ("if during ", "what happens if you are not sure", "in footnote", "adobe reader")
    return not any(item in value.casefold() for item in blocked)
