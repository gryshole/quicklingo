from __future__ import annotations

import re

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.learning.card_display import display_term, is_english_example, parse_context, serialize_context

_PROMPT_TEXT_LIMIT = 160
_UA_EN_EXAMPLE_COUNT = 3
_EXAMPLE_COUNT = _UA_EN_EXAMPLE_COUNT
_WORD_RE = re.compile(r"[\w']+", re.UNICODE)
_STOPWORDS = frozenset(
    "a an the to of in on at for and or but is are was were be been being "
    "that this it its from with as by not".split()
)
_BOILERPLATE_RE = re.compile(
    r"(?i)загальна\s+назва|general\s+(term|name)\s+for|"
    r"this\s+is\s+a\s+(word|term)\s+(for|that)"
)
_DEFINITIONAL_PATTERNS = (
    r"(?i)людина,\s*яка",
    r"(?i)це\s+коли",
    r"(?i)означає",
    r"(?i)визначення",
    r"(?i)situation\s+that",
    r"(?i)a\s+person\s+who",
    r"(?i)something\s+that",
    r"(?i)щось\s",
    r"(?i)something\s",
)
_CONTEXT_DEFINITIONAL_PATTERNS = _DEFINITIONAL_PATTERNS + (
    r"(?i)^про\s",
    r"(?i)загальна\s",
    r"(?i),\s*що\s",
    r"(?i)фізична\s+або\s+психічна",
)
_SIMILARITY_THRESHOLD = 0.6
_NOTES_MAX_LEN = 120
_ROOT_PREFIX_MIN = 5
_HINT_UK_WHITELIST = frozenset(
    {
        "іменник",
        "дієслово",
        "прикметник",
        "прислівник",
        "формальний",
        "неформальний",
        "formal",
        "informal",
        "результат",
        "процес",
        "дія",
        "властивість",
        "характеристика",
        "поняття",
        "недолік",
        "людина",
        "думка",
        "абстрактне",
        "укр",
        "вираз",
        "сл",
        "слова",
    }
)
_LATIN_INITIAL_RE = re.compile(r"(?:^|[·\s])([a-z])…", re.IGNORECASE)
_CYRILLIC_WORD_RE = re.compile(r"[\u0400-\u04FF]+")
_GENERIC_POS_RE = re.compile(
    r"(?i)(укр\.\s*(?:слово|вираз)|англ\.\s*(?:слово|вираз)|general\s+term|\bтермін\b|\bterm\b|\bword\b)"
)


DEFAULT_CARD_PROMPT_UA_EN = """You analyze translation history from real-world usage — TV series, client meetings, work chat, emails, and any other context where the learner looked up a word or phrase. Create flashcards for active recall training.

Corpus tag: {tag}
Translation direction: {direction}

Return ONLY valid JSON with this schema:
{{"cards":[{{"front":"...","back":"...","context":["...","...","..."],"hint":"...","notes":"...","quizDistractors":["...","...","...","..."],"priority":1-5,"source_record_id":123,"imageable":true,"image_prompt":"..."}}],"summary":{{"themes":["..."],"recommended_daily_count":20,"total_unique":0,"comment":"..."}}}}

Review UX — what the learner sees:
- BEFORE answering: front + hint only.
- AFTER answering: back + notes + context (three English example sentences).

Card field rules (each field has a DISTINCT role — never duplicate the same idea):
- front: short term in the SOURCE language (from source=). No full sentence.
- back: translation in the TARGET language (from result=) — the ANSWER to recall.
- hint: meta-clue toward the TARGET (back) language — shown BEFORE the answer. Must NOT define or paraphrase front.
- context: array of exactly 3 short ENGLISH usage sentences shown after notes — each MUST contain back. Use varied contexts/collocations. NEVER Ukrainian sentences.
- notes: ONE short English A2–B2 definition of back (max 1 sentence). MUST start with "Definition:". Shown AFTER the answer in a gray pill.

{direction_rules}

Hint rules (CRITICAL — active recall must stay hard):
- hint MUST start with the correct part of speech for front (Ukrainian labels): іменник, дієслово, прикметник, прислівник, фразовий дієслівник. Never default to прикметник.
- hint must NOT define or paraphrase front — no Ukrainian/English definitions, synonyms, near-synonyms, or shared roots with front.
- FORBIDDEN: shared root/morpheme with front (неминуче for неминучий, гірше for погіршувати), patterns like "щось …" or "something …".
- hint must NOT contain any significant word from back (no shared content words of 4+ letters, no substring of back).
- Never use template phrases like "Загальна назва для…" or "General term for…".
- Good hints: correct POS + register + semantic domain + letter pattern (NOT pseudo-definitions).
- Bad hints: wrong POS, defining front, quoting back, near-synonyms that ARE the answer.

Context rules:
- context MUST be a JSON array of exactly 3 short English sentences. Each sentence MUST contain back (the English target word).
- Use different contexts or collocations across the three sentences. Keep each sentence under ~80 characters.
- Each sentence MUST include other words before AND after back — real usage in a full sentence.
- FORBIDDEN: context lines that are only back with optional punctuation (e.g. "biased." or "to bite the bullet.") — no term-only lines.
- DO NOT write Ukrainian sentences, dictionary definitions, or meta-phrases describing the word.
- Never use "General term for…" or similar definitional templates.

Notes rules:
- Write a simple English A2–B2 definition of back in max ~100 characters.
- Format: "Definition: <short definition>" — usage examples belong in context, not notes.
- FORBIDDEN: ≠ symbol, antonyms, comparisons, collocation-only lines, full example sentences.
- Never repeat hint or any context sentence. Never use "Загальна назва для…".
- Good: "Definition: not enough of something that is needed"
- Bad: "≠ lack (general)"; long explanations; repeating context sentences.

Quiz distractor rules (quizDistractors):
- JSON array of 3–5 ENGLISH words only — same part of speech as back (the English target word).
- Same topic/category as back, but a CLEARLY DIFFERENT specific meaning — not interchangeable in your context sentences.
- CRITICAL: NEVER use exact synonyms or near-synonyms of back.
- CRITICAL: NEVER use words that grammatically and contextually fit the blank in your example sentences.
- Substitution Test (MANDATORY): mentally replace back with each distractor in EVERY context sentence. The new sentence must become factually false, logically absurd, or clearly wrong — not "also plausible".
  - FAIL for back=biased, sentence "The judge was ___ toward the defendant", distractor partial (partial fits perfectly).
  - PASS for back=biased, same sentence, distractor inexperienced (different meaning, not a synonym).
  - FAIL for back=apple, sentence "He picked an ___ from the tree", distractor orange (orange fits).
  - PASS for back=apple, sentence "Newton discovered gravity when an ___ fell on his head", distractor orange (factually wrong).
- FORBIDDEN: back itself, Ukrainian text, full sentences, duplicates.

Example good cards (ua-en):
{{"front":"Упереджений","back":"biased","hint":"прикметник · людина/думка · formal · b… i…","context":["The judge was biased toward the defendant.","Avoid biased opinions in your report.","He gave a biased account of events."],"notes":"Definition: unfairly favouring one side or opinion","quizDistractors":["honest","strict","inexperienced","neutral"],"priority":4,"source_record_id":123,"imageable":false,"image_prompt":""}}
{{"front":"Погіршувати","back":"worsen","hint":"дієслово · процес · formal · w… n…","context":["The pain may worsen after exercise.","Bad weather could worsen the situation.","Delays will worsen the backlog."],"notes":"Definition: to become worse or more serious","quizDistractors":["improve","stabilize","reduce","prevent"],"priority":3,"source_record_id":124,"imageable":false,"image_prompt":""}}
{{"front":"витривалість","back":"endurance","hint":"іменник · властивість · formal · e… n…","context":["She showed great endurance on the final lap.","Marathon training builds endurance.","His endurance surprised everyone."],"notes":"Definition: ability to keep going despite difficulty","quizDistractors":["speed","strength","height","courage"],"priority":3,"source_record_id":126,"imageable":false,"image_prompt":""}}
{{"front":"банк","back":"bank","hint":"іменник · фінанси · formal · b… k…","context":["She opened a bank account yesterday.","The bank approved the loan.","He works at a local bank."],"notes":"Definition: a business that holds money for customers","quizDistractors":["treasury","credit union","fund","vault"],"priority":3,"source_record_id":128,"imageable":false,"image_prompt":""}}
{{"front":"дефіцит","back":"shortage","hint":"іменник · нестача · formal · s… h…","context":["The shortage of food caused a crisis.","The company faced a shortage of skilled workers.","The shortage of water affected the crops."],"notes":"Definition: not enough of something that is needed","quizDistractors":["deficit","scarcity","gap","limit"],"priority":3,"source_record_id":127,"imageable":false,"image_prompt":""}}

imageable / image_prompt:
- imageable: true only when a simple visual helps memory; else false.
- image_prompt: English scene description for image search (concrete nouns / visual metaphors).

Quality:
- Keep front and back under 80 characters. Escape double quotes inside strings as \\".
- Merge duplicate terms. priority 5 = most important for a learner.
- Every card MUST have a non-empty hint, context array (3 English sentences), notes (English definition of back), and quizDistractors (3–5 English words).

Items (source = front language, result = back language):
{items}"""

DEFAULT_CARD_PROMPT_EN_UA = """You analyze translation history from real-world usage — TV series, client meetings, work chat, emails, and any other context where the learner looked up a word or phrase. Create flashcards for active recall training.

Corpus tag: {tag}
Translation direction: en-ua (English front → Ukrainian back)

Return ONLY valid JSON with this schema:
{{"cards":[{{"front":"...","back":"...","context":["...","...","..."],"hint":"...","notes":"...","quizDistractors":["...","...","...","..."],"priority":1-5,"source_record_id":123,"imageable":true,"image_prompt":"..."}}],"summary":{{"themes":["..."],"recommended_daily_count":20,"total_unique":0,"comment":"..."}}}}

Review UX — what the learner sees:
- BEFORE answering: English front + hint only.
- AFTER answering: Ukrainian back + English definition (notes) + context (three English example sentences).

Card field rules (each field has a DISTINCT role — never duplicate the same idea):
- front: short English term/phrase (from source=). No full sentence.
- back: Ukrainian translation (from result=) — the ANSWER to recall.
- hint: meta-clue toward Ukrainian back — shown BEFORE the answer. Must NOT define or paraphrase front.
- notes: ONE short English A2–B2 definition of front (max 1 sentence). MUST start with "Definition:". Shown AFTER the answer in a gray pill.
- context: array of exactly 3 short ENGLISH usage sentences shown after notes — each MUST contain front. Use varied contexts/collocations.

Hint rules (CRITICAL — active recall must stay hard):
- hint MUST help recall Ukrainian back, NEVER English front.
- Start with Ukrainian OR English part of speech (прикметник / adjective, дієслово / verb…) + register + broad semantic category (результат, процес, недолік, властивість, абстрактне поняття…).
- NEVER use generic labels like "укр. слово", "укр. вираз", "термін", "word", or "term". You MUST start hint with one of: іменник, дієслово, прикметник, прислівник, ідіома (multi-word front → ідіома).
- Letter pattern (CRITICAL): use first letter(s) of back (Ukrainian words), NEVER Latin initials from front. Example: inevitable / невідворотний → "… · н…" NOT "i… n…".
- FORBIDDEN: any Ukrainian lemma from back or a direct synonym (e.g. back=хиба → never "вада" in hint).
- FORBIDDEN: English definitions, paraphrases of front, shared roots with front, template phrases like "General term for…".
- Never use pseudo-definitions or near-synonyms that ARE the answer.

Context rules:
- context MUST be a JSON array of exactly 3 short English sentences. Each sentence MUST contain front (the English source word).
- Use different contexts or collocations across the three sentences. Keep each sentence under ~80 characters.
- Each sentence MUST include other words before AND after front — real usage in a full sentence.
- FORBIDDEN: context lines that are only front with optional punctuation (e.g. "inevitable." or "to bite the bullet.") — no term-only lines.
- Primary: copy or adapt real sentences from source= when available; invent natural examples if source= is only a word.
- DO NOT write dictionary definitions, explanations, or meta-phrases describing the word.
- Never use "General term for…" or similar definitional templates.

Notes rules:
- Write a simple English A2–B2 definition of front in max ~100 characters.
- Format: "Definition: <short definition>" — the learner already sees Ukrainian back; usage examples belong in context, not notes.
- Never repeat hint or any context sentence. Never use boilerplate like "General term for…".
- Good: "Definition: certain to happen; cannot be avoided"
- Bad: Ukrainian text in notes; long explanations; repeating context sentences.

Quiz distractor rules (quizDistractors):
- JSON array of 3–5 ENGLISH words only — same part of speech as front (the English source word).
- Same topic/category as front, but a CLEARLY DIFFERENT specific meaning — not interchangeable in your context sentences.
- CRITICAL: NEVER use exact synonyms or near-synonyms of front.
- CRITICAL: NEVER use words that grammatically and contextually fit the blank in your example sentences.
- Substitution Test (MANDATORY): mentally replace front with each distractor in EVERY context sentence. The new sentence must become factually false, logically absurd, or clearly wrong — not "also plausible".
  - FAIL for front=biased, sentence "The judge was ___ toward the defendant", distractor partial.
  - PASS for front=biased, same sentence, distractor inexperienced.
  - FAIL for front=apple, sentence "He picked an ___ from the tree", distractor orange.
  - PASS for front=apple, sentence "Newton discovered gravity when an ___ fell on his head", distractor orange.
- FORBIDDEN: front itself, Ukrainian text, full sentences, duplicates.

Example good cards (en-ua):
{{"front":"inevitable","back":"невідворотний","hint":"прикметник · результат · formal · н…","context":["The decline seemed inevitable.","Change felt inevitable after the vote.","It was inevitable that costs would rise."],"notes":"Definition: certain to happen; cannot be avoided","quizDistractors":["predictable","expected","likely","certain"],"priority":4,"source_record_id":123,"imageable":false,"image_prompt":""}}
{{"front":"flaw","back":"хиба","hint":"іменник · недолік · formal · х…","context":["The report revealed a serious flaw.","This flaw could affect the whole system.","They fixed the flaw before launch."],"notes":"Definition: a fault or weakness in something","quizDistractors":["advantage","feature","benefit","strength"],"priority":3,"source_record_id":124,"imageable":false,"image_prompt":""}}
{{"front":"exacerbate","back":"загострювати","hint":"дієслово · процес · formal · з…","context":["The new policy will exacerbate the problem.","Stress can exacerbate existing symptoms.","Delays may exacerbate the backlog."],"notes":"Definition: to make a problem or bad situation worse","quizDistractors":["improve","stabilize","reduce","prevent"],"priority":3,"source_record_id":125,"imageable":false,"image_prompt":""}}
{{"front":"bank","back":"банк","hint":"іменник · фінанси · formal · б…","context":["She opened a bank account yesterday.","The bank approved the loan.","He works at a local bank."],"notes":"Definition: a business that holds money for customers","quizDistractors":["treasury","credit union","fund","vault"],"priority":3,"source_record_id":126,"imageable":false,"image_prompt":""}}

imageable / image_prompt:
- imageable: true only when a simple visual helps memory; else false.
- image_prompt: English scene description for image search (concrete nouns / visual metaphors).

Quality:
- Keep front and back under 80 characters. Escape double quotes inside strings as \\".
- Merge duplicate terms. priority 5 = most important for a learner.
- Every card MUST have a non-empty hint, context array (3 English sentences), notes (English definition), and quizDistractors (3–5 English words).

Items (source = English, result = Ukrainian):
{items}"""


def direction_hint_rules(direction: str) -> str:
    kind = resolve_learning_direction(direction)
    if kind == "ua-en":
        return (
            "Direction ua-en (Ukrainian front → English back):\n"
            "- front = Ukrainian term/phrase (from source=).\n"
            "- back = English translation (from result=) — the learner must recall this.\n"
            "- hint: meta-clue toward ENGLISH back — NEVER define or paraphrase the Ukrainian front.\n"
            "- hint MUST start with correct POS for front: іменник, дієслово, прикметник, прислівник, or фразовий дієслівник. Never default to прикметник.\n"
            "- Priority for hint (use first that fits):\n"
            "  1. Correct POS + domain + register (e.g. \"дієслово · процес · formal\").\n"
            "  2. English circumlocution with DIFFERENT words (never words from back).\n"
            "  3. Last resort only: word count + first-letter pattern (e.g. \"англ. слово · b… i…\").\n"
            "- FORBIDDEN in hint: wrong POS, Ukrainian definitions of front, shared roots with front, \"щось …\", \"Загальна назва для…\".\n"
            "- context: JSON array of 3 short ENGLISH sentences with back — varied contexts/collocations; each sentence needs words before AND after back (never back alone with punctuation).\n"
            "- notes: English Definition of back (A2–B2); format \"Definition: …\"; no ≠, antonyms, or example sentences.\n"
        )
    if kind == "en-ua":
        return (
            "Direction en-ua (English front → Ukrainian back):\n"
            "- front = English (from source=).\n"
            "- back = Ukrainian translation (from result=).\n"
            "- hint: meta-clue toward Ukrainian back — NEVER define or paraphrase the English front.\n"
            "- Prefer: English grammar label, register, semantic category, or first-letter pattern for Ukrainian back.\n"
            "- Never use Ukrainian words from back in hint.\n"
            "- context: JSON array of 3 short ENGLISH sentences with front — varied contexts/collocations; each sentence needs words before AND after front (never front alone with punctuation).\n"
            "- notes: English Definition line; must not duplicate any context sentence.\n"
        )
    return (
        f"Direction {direction}:\n"
        "- hint must not define front or leak words from back into the pre-answer clue.\n"
        "- context: corpus sentence; notes: usage in target language without duplicating hint/context."
    )


def get_builtin_card_prompt_template(direction: str = "ua-en") -> str:
    if resolve_learning_direction(direction) == "en-ua":
        return DEFAULT_CARD_PROMPT_EN_UA
    return DEFAULT_CARD_PROMPT_UA_EN


def get_card_prompt_template(direction: str = "ua-en") -> str:
    from quicklingo.features import get_feature

    feature = get_feature("learning.ai_corpus_analysis")
    norm = resolve_learning_direction(direction)
    if norm == "en-ua":
        custom = feature.get("card_prompt_template_en_ua", "")
    else:
        custom = feature.get("card_prompt_template_ua_en", "")
        if not (isinstance(custom, str) and custom.strip()):
            custom = feature.get("card_prompt_template", "")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    return get_builtin_card_prompt_template(norm)


def _clip_prompt_text(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= _PROMPT_TEXT_LIMIT:
        return cleaned
    return cleaned[: _PROMPT_TEXT_LIMIT - 1] + "…"


def format_items_block(candidates) -> str:
    lines: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        source = _clip_prompt_text(candidate.source_text)
        result = _clip_prompt_text(candidate.result_text)
        lines.append(
            f"{index}. id={candidate.record_id} [{candidate.reason}] "
            f"source={source} result={result}"
        )
    return "\n".join(lines)


def build_card_analysis_prompt(
    candidates: list[CorpusCandidate],
    *,
    tag: str,
    direction: str,
) -> str:
    template = get_card_prompt_template(direction)
    if "{direction_rules}" in template:
        template = template.replace("{direction_rules}", direction_hint_rules(direction))
    return (
        template.replace("{tag}", tag or "")
        .replace("{direction}", direction)
        .replace("{items}", format_items_block(candidates))
    )


def _content_tokens(text: str, *, min_len: int = 4) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(text)
        if len(token) >= min_len and token.lower() not in _STOPWORDS
    }


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def is_boilerplate(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_BOILERPLATE_RE.search(cleaned))


def is_definitional_context(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return any(re.search(pattern, cleaned) for pattern in _CONTEXT_DEFINITIONAL_PATTERNS)


def texts_too_similar(a: str, b: str) -> bool:
    a_norm = _normalize_text(a)
    b_norm = _normalize_text(b)
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True
    if a_norm in b_norm or b_norm in a_norm:
        return True
    tokens_a = _content_tokens(a, min_len=3)
    tokens_b = _content_tokens(b, min_len=3)
    if not tokens_a or not tokens_b:
        return False
    overlap = tokens_a & tokens_b
    ratio = len(overlap) / min(len(tokens_a), len(tokens_b))
    return ratio >= _SIMILARITY_THRESHOLD


def hint_spoils_answer(hint: str, back: str) -> bool:
    hint = hint.strip()
    back = back.strip()
    if not hint or not back:
        return False
    hint_lower = hint.lower()
    back_lower = back.lower()
    if len(back_lower) >= 5 and back_lower in hint_lower:
        return True
    if len(hint_lower) >= 5 and hint_lower in back_lower:
        return True
    hint_tokens = _content_tokens(hint)
    back_tokens = _content_tokens(back)
    if not hint_tokens or not back_tokens:
        return False
    overlap = hint_tokens & back_tokens
    if overlap:
        return True
    return len(overlap) / max(1, len(hint_tokens)) >= 0.34


def hint_spoils_front(hint: str, front: str) -> bool:
    hint = hint.strip()
    front = front.strip()
    if not hint or not front:
        return False
    if is_boilerplate(hint):
        return True
    hint_lower = hint.lower()
    front_lower = front.lower()
    if len(front_lower) >= 4 and front_lower in hint_lower:
        return True
    for pattern in _DEFINITIONAL_PATTERNS:
        if re.search(pattern, hint):
            return True
    front_tokens = _content_tokens(front, min_len=3)
    hint_tokens = _content_tokens(hint, min_len=3)
    if not front_tokens or not hint_tokens:
        return False
    overlap = front_tokens & hint_tokens
    if overlap and len(overlap) / max(1, len(front_tokens)) >= 0.5:
        return True
    return len(overlap) / max(1, len(hint_tokens)) >= 0.34


def _shared_prefix_len(a: str, b: str) -> int:
    count = 0
    for left, right in zip(a, b):
        if left != right:
            break
        count += 1
    return count


def hint_shares_root(hint: str, front: str) -> bool:
    hint = hint.strip().lower()
    front = front.strip().lower()
    if not hint or not front:
        return False
    hint_tokens = _WORD_RE.findall(hint)
    front_tokens = _WORD_RE.findall(front)
    candidates = front_tokens + [front.replace(" ", "")]
    for hint_token in hint_tokens:
        if len(hint_token) < 4:
            continue
        for front_token in candidates:
            if len(front_token) < 4:
                continue
            if _shared_prefix_len(hint_token, front_token) >= _ROOT_PREFIX_MIN:
                return True
            if hint_token in front_token or front_token in hint_token:
                if min(len(hint_token), len(front_token)) >= 4:
                    return True
    return False


def _expected_pos_category(front: str) -> str:
    front = front.strip()
    if not front:
        return "other"
    if " " in front:
        return "phrasal"
    lower = front.lower()
    if any(lower.endswith(suffix) for suffix in ("увати", "ити", "ати", "яти", "еть")):
        return "verb"
    if any(lower.endswith(suffix) for suffix in ("ість", "ство", "ція", "ення")):
        return "noun"
    if lower.endswith(("ий", "ій", "а", "е")):
        return "adjective"
    return "other"


def hint_pos_mismatch(hint: str, front: str) -> bool:
    hint_lower = hint.lower()
    category = _expected_pos_category(front)
    if category == "verb":
        return "прикметник" in hint_lower and "дієслов" not in hint_lower
    if category == "phrasal":
        return (
            "прикметник" in hint_lower
            and "фразов" not in hint_lower
            and "дієслов" not in hint_lower
            and "вираз" not in hint_lower
        )
    if category == "noun":
        return "прикметник" in hint_lower and "іменник" not in hint_lower
    if category == "adjective":
        return "дієслов" in hint_lower and "прикметник" not in hint_lower
    return False


def hint_uses_front_letters(hint: str, front: str) -> bool:
    hint = hint.strip()
    front = front.strip()
    if not hint or not front:
        return False
    front_initials = {
        word[0].lower()
        for word in _WORD_RE.findall(front)
        if word and word[0].isascii() and word[0].isalpha()
    }
    if not front_initials:
        return False
    return any(match.group(1).lower() in front_initials for match in _LATIN_INITIAL_RE.finditer(hint))


def _uk_lemma_allowed_in_hint(token: str, back_lower: str) -> bool:
    lowered = token.lower()
    if lowered in _HINT_UK_WHITELIST:
        return True
    if lowered in back_lower:
        return True
    return any(
        lowered.startswith(prefix)
        for prefix in ("іменник", "дієслов", "прикметник", "прислівник", "фразов")
    )


def hint_has_forbidden_uk_lemma(hint: str, back: str) -> bool:
    back_lower = back.lower()
    for token in _CYRILLIC_WORD_RE.findall(hint):
        if len(token) < 3:
            continue
        if _uk_lemma_allowed_in_hint(token, back_lower):
            continue
        return True
    return False


def hint_uses_generic_pos_label(hint: str) -> bool:
    return bool(_GENERIC_POS_RE.search(hint.strip()))


def _expected_pos_category_en(front: str) -> str:
    front = front.strip()
    if not front:
        return "other"
    if " " in front:
        return "idiom"
    lower = front.lower()
    if lower.endswith("ly"):
        return "adverb"
    if any(lower.endswith(suffix) for suffix in ("ate", "ify", "ize", "ise")):
        return "verb"
    if any(
        lower.endswith(suffix)
        for suffix in ("tion", "ness", "ment", "ity", "ism", "ship", "ance", "ence", "sion")
    ):
        return "noun"
    if any(
        lower.endswith(suffix) for suffix in ("ous", "ful", "ive", "able", "ible", "al", "ic", "ed", "ing")
    ):
        return "adjective"
    return "other"


def _en_ua_pos_prefix(front: str) -> str:
    mapping = {
        "noun": "іменник",
        "verb": "дієслово",
        "adjective": "прикметник",
        "adverb": "прислівник",
        "idiom": "ідіома",
        "other": "іменник",
    }
    return mapping[_expected_pos_category_en(front)]


def _ua_pos_prefix(front: str) -> str:
    mapping = {
        "verb": "дієслово",
        "phrasal": "фразовий дієслівник",
        "adjective": "прикметник",
        "noun": "іменник",
    }
    return mapping.get(_expected_pos_category(front), "")


def _initials_pattern(back: str) -> str:
    words = [word for word in _WORD_RE.findall(back) if word][:6]
    if not words:
        return ""
    if len(words) == 1:
        return f"{words[0][0].lower()}…"
    return " · ".join(f"{word[0].lower()}…" for word in words)


def fallback_hint(front: str, back: str, direction: str) -> str:
    kind = resolve_learning_direction(direction)
    words = _WORD_RE.findall(back)
    count = len(words)
    initials = _initials_pattern(back)

    if kind == "ua-en":
        if count >= 3:
            base = f"англ. вираз · {count} сл."
        elif count == 2:
            base = "англ. вираз · 2 сл."
        else:
            base = "англ. слово"
        pos = _ua_pos_prefix(front)
        if pos:
            base = f"{pos} · {base}"
        if initials:
            return f"{base} · {initials}"
        return base

    if kind == "en-ua":
        pos = _en_ua_pos_prefix(front)
        if count >= 3:
            base = f"{pos} · {count} сл."
        elif count == 2:
            base = f"{pos} · 2 сл."
        else:
            base = f"{pos} · formal"
        if initials:
            return f"{base} · {initials}"
        return base

    if initials:
        return f"{count} words · {initials}"
    return f"{count} word(s)" if count else "recall translation"


def sanitize_hint(hint: str, *, front: str, back: str, direction: str) -> str:
    kind = resolve_learning_direction(direction)
    cleaned = " ".join(hint.split()).strip()
    if cleaned:
        if hint_spoils_answer(cleaned, back):
            return fallback_hint(front, back, direction)
        if hint_spoils_front(cleaned, front):
            return fallback_hint(front, back, direction)
        if hint_shares_root(cleaned, front):
            return fallback_hint(front, back, direction)
        if kind != "en-ua" and hint_pos_mismatch(cleaned, front):
            return fallback_hint(front, back, direction)
        if kind == "en-ua":
            if hint_uses_front_letters(cleaned, front):
                return fallback_hint(front, back, direction)
            if hint_has_forbidden_uk_lemma(cleaned, back):
                return fallback_hint(front, back, direction)
            if hint_uses_generic_pos_label(cleaned):
                return fallback_hint(front, back, direction)
        return cleaned
    return fallback_hint(front, back, direction)


def _sanitize_context(context: str, *, direction: str = "ua-en") -> str:
    cleaned = " ".join(context.split()).strip()
    if not cleaned or is_boilerplate(cleaned):
        return ""
    if resolve_learning_direction(direction) == "ua-en" and is_definitional_context(cleaned):
        return ""
    return cleaned


def _looks_like_usage_sentence(text: str, *, direction: str = "ua-en") -> bool:
    cleaned = " ".join(text.split()).strip()
    if not cleaned or is_boilerplate(cleaned):
        return False
    if resolve_learning_direction(direction) == "ua-en" and is_definitional_context(cleaned):
        return False
    words = _WORD_RE.findall(cleaned)
    if len(words) >= 3:
        return True
    return bool(re.search(r"[.!?…]", cleaned))


def _text_contains_term(text: str, term: str) -> bool:
    if not text or not term:
        return False
    return term.lower() in text.lower()


def _corpus_context_from_source(
    source_text: str,
    front: str,
    *,
    direction: str = "ua-en",
) -> str:
    cleaned = " ".join(source_text.split()).strip()
    if not cleaned or not _looks_like_usage_sentence(cleaned, direction=direction):
        return ""
    if not _text_contains_term(cleaned, front):
        return ""
    return _sanitize_context(cleaned, direction=direction)


def fallback_context(front: str, back: str, direction: str) -> str:
    if resolve_learning_direction(direction) == "en-ua":
        if " " in front:
            return f"We need to consider {front} before deciding."
        return f"The outcome seemed {front} given the circumstances."
    return ""


def fallback_english_examples(term: str) -> list[str]:
    term = term.strip()
    if not term:
        return []
    if " " in term:
        return [
            f"I don't want to {term} yet.",
            f"They tried to {term} last week.",
            f"It's hard to {term} now.",
        ]
    return [
        f"The result was {term}.",
        f"Good {term} matters here.",
        f"We discussed {term} in the meeting.",
    ]


def fallback_ua_en_examples(back: str) -> list[str]:
    return fallback_english_examples(back)


def _coerce_context_input(context: object, *, direction: str) -> list[str]:
    if isinstance(context, list):
        return [str(item).strip() for item in context if str(item).strip()]
    if isinstance(context, str):
        return parse_context(context, direction=direction)
    return []


def _sanitize_english_example(sentence: str, *, term: str) -> str:
    cleaned = " ".join(sentence.split()).strip()
    if not cleaned or is_boilerplate(cleaned):
        return ""
    if not is_english_example(cleaned):
        return ""
    if not _text_contains_term(cleaned, term):
        return ""
    if not cleaned.endswith((".", "!", "?")):
        cleaned += "."
    return cleaned


def _append_example(
    results: list[str],
    seen: set[str],
    sentence: str,
    *,
    term: str,
) -> None:
    cleaned = _sanitize_english_example(sentence, term=term)
    key = cleaned.lower()
    if cleaned and key not in seen:
        seen.add(key)
        results.append(cleaned)


def ensure_english_examples(
    context: object,
    *,
    term: str,
    direction: str = "ua-en",
    source_text: str = "",
    front: str = "",
) -> list[str]:
    term = term.strip()
    kind = resolve_learning_direction(direction)
    seen: set[str] = set()
    results: list[str] = []

    if kind == "en-ua" and source_text:
        corpus = _corpus_context_from_source(
            source_text,
            front or term,
            direction=direction,
        )
        if corpus:
            _append_example(results, seen, corpus, term=term)

    for item in _coerce_context_input(context, direction=direction):
        _append_example(results, seen, item, term=term)
        if len(results) >= _EXAMPLE_COUNT:
            return results[:_EXAMPLE_COUNT]

    for candidate in fallback_english_examples(term):
        _append_example(results, seen, candidate, term=term)
        if len(results) >= _EXAMPLE_COUNT:
            break
    return results[:_EXAMPLE_COUNT]


def ensure_ua_en_examples(context: object, *, back: str) -> list[str]:
    return ensure_english_examples(context, term=back, direction="ua-en")


def ensure_context(
    context: str,
    *,
    front: str,
    back: str,
    direction: str = "ua-en",
    source_text: str = "",
) -> str:
    cleaned = _sanitize_context(context, direction=direction)
    if cleaned:
        return cleaned
    from_corpus = _corpus_context_from_source(
        source_text,
        front,
        direction=direction,
    )
    if from_corpus:
        return from_corpus
    return fallback_context(front, back, direction)


def _truncate_notes(notes: str, *, max_len: int = _NOTES_MAX_LEN) -> str:
    cleaned = " ".join(notes.split()).strip()
    if len(cleaned) <= max_len:
        return cleaned
    truncated = cleaned[:max_len]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated.rstrip(".,;") + "…"


def _normalize_definition_notes(notes: str) -> str:
    cleaned = " ".join(notes.split()).strip()
    if not cleaned:
        return ""
    lower = cleaned.lower()
    if lower.startswith("definition:"):
        return cleaned
    if lower.startswith("def:"):
        body = cleaned[4:].lstrip()
        return f"Definition: {body}"
    return f"Definition: {cleaned}"


def _normalize_en_ua_notes(notes: str) -> str:
    return _normalize_definition_notes(notes)


def _is_legacy_contrast_notes(notes: str) -> bool:
    cleaned = " ".join(notes.split()).strip()
    if not cleaned:
        return False
    lower = cleaned.lower()
    if lower.startswith("definition:"):
        return False
    if cleaned.startswith("≠") or cleaned.startswith("!="):
        return True
    if "≠" in cleaned or "!=" in cleaned:
        return True
    return False


def _sanitize_notes(
    notes: str,
    *,
    hint: str,
    context: str,
    front: str,
    back: str = "",
    direction: str = "ua-en",
    context_examples: list[str] | None = None,
) -> str:
    kind = resolve_learning_direction(direction)
    cleaned = " ".join(notes.split()).strip()
    if not cleaned or is_boilerplate(cleaned):
        return ""
    if _is_legacy_contrast_notes(cleaned):
        return ""
    examples = context_examples or parse_context(context, direction=kind)
    for example in examples:
        if texts_too_similar(cleaned, example):
            return ""
    if texts_too_similar(cleaned, hint):
        return ""
    if kind == "ua-en" and texts_too_similar(cleaned, front):
        return ""
    cleaned = _normalize_definition_notes(cleaned)
    return _truncate_notes(cleaned)


def enrich_card_fields(
    card: dict,
    *,
    direction: str = "ua-en",
    source_text: str = "",
    quiz_pool: list[str] | None = None,
) -> dict:
    """Fill and sanitize hint/notes for active-recall-friendly cards."""
    hint = str(card.get("hint", "")).strip()
    notes = str(card.get("notes", "")).strip()
    raw_context = card.get("context", "")
    back = str(card.get("back", "")).strip()
    front = display_term(str(card.get("front", "")))
    kind = resolve_learning_direction(direction)

    term = back if kind == "ua-en" else front
    examples = ensure_english_examples(
        raw_context,
        term=term,
        direction=kind,
        source_text=source_text,
        front=front,
    )
    context = serialize_context(examples, direction=kind)

    sanitized_hint = sanitize_hint(hint, front=front, back=back, direction=kind)
    notes = _sanitize_notes(
        notes,
        hint=sanitized_hint,
        context=context,
        front=front,
        back=back,
        direction=kind,
        context_examples=examples,
    )

    card["hint"] = sanitized_hint
    card["front"] = front
    card["context"] = context
    card["notes"] = notes

    from quicklingo.db import learning as learning_db
    from quicklingo.learning.quiz.distractors import serialize_quiz_distractors

    pos = extract_pos_from_hint(sanitized_hint)
    if quiz_pool is not None:
        pool = [word for word in quiz_pool if word.lower() != term.lower()]
    else:
        pool = learning_db.list_quiz_english_words(pos_prefix=pos, exclude={term})
    raw_distractors = card.get("quizDistractors") or card.get("quiz_distractors")
    distractors = ensure_quiz_distractors(
        raw_distractors,
        term=term,
        hint=sanitized_hint,
        definition=notes,
        examples=examples,
        pool=pool,
    )
    card["quiz_distractors"] = serialize_quiz_distractors(distractors)
    return card


_POS_ALIASES: dict[str, tuple[str, ...]] = {
    "іменник": ("іменник", "noun"),
    "дієслово": ("дієслово", "verb"),
    "прикметник": ("прикметник", "adjective"),
    "прислівник": ("прислівник", "adverb"),
    "фразовий дієслівник": ("фразовий дієслівник", "phrasal verb"),
    "ідіома": ("ідіома", "idiom"),
}


def extract_pos_from_hint(hint: str) -> str:
    cleaned = (hint or "").strip().lower()
    if not cleaned:
        return ""
    first = cleaned.split("·", 1)[0].strip()
    for canonical, aliases in _POS_ALIASES.items():
        if first in aliases or any(alias in first for alias in aliases):
            return canonical
    return first


def hint_pos_matches(hint: str, pos_prefix: str) -> bool:
    if not pos_prefix:
        return True
    hint_pos = extract_pos_from_hint(hint).lower()
    target = pos_prefix.lower()
    if not hint_pos:
        return False
    if hint_pos == target or hint_pos.startswith(target) or target.startswith(hint_pos):
        return True
    aliases = _POS_ALIASES.get(target, (target,))
    return any(alias in hint_pos for alias in aliases)


def ensure_quiz_distractors(
    raw: object,
    *,
    term: str,
    hint: str,
    definition: str,
    examples: list[str],
    pool: list[str],
) -> list[str]:
    from quicklingo.learning.quiz.distractors import (
        distractor_passes_basic_validation,
        fallback_quiz_distractors,
        parse_quiz_distractors,
    )

    term_key = term.strip().lower()
    candidates = parse_quiz_distractors(raw)
    cleaned: list[str] = []
    seen: set[str] = {term_key}
    for word in candidates:
        key = word.lower()
        if key in seen:
            continue
        if _CYRILLIC_WORD_RE.search(word):
            continue
        if texts_too_similar(word, hint):
            continue
        if not distractor_passes_basic_validation(term, word, definition):
            continue
        seen.add(key)
        cleaned.append(word)
    pos = extract_pos_from_hint(hint)
    if len(cleaned) < 3:
        needed = 5 - len(cleaned)
        for word in fallback_quiz_distractors(
            term,
            pos,
            pool,
            count=max(needed, 3),
            examples=examples,
            definition=definition,
            check_examples=False,
        ):
            key = word.lower()
            if key in seen:
                continue
            if texts_too_similar(word, hint):
                continue
            seen.add(key)
            cleaned.append(word)
            if len(cleaned) >= 5:
                break
    return cleaned[:5]
