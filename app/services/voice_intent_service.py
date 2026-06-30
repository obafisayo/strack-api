"""Voice command -> intent matching.

Deterministic keyword matching, not ML - cheap, fast, and predictable, which
matters most for CONFIRM/CANCEL on a destructive action. Pure function, no DB,
unit-tested like goal_service/streak_service.

CAVEAT: the Yoruba/Igbo/Hausa/Pidgin phrases below are my best-effort
translations, not reviewed by a native speaker of each language (same
honesty as the YarnGPT voice-mapping caveat elsewhere in this codebase). If
real users report commands not being recognized, this dictionary - the only
place these phrases live - is what to correct first, ideally with native
speaker review before relying on it in production.
"""

import enum
import re
import unicodedata


class Intent(str, enum.Enum):
    QUERY_STEPS = "query_steps"
    QUERY_STREAK = "query_streak"
    QUERY_LEADERBOARD = "query_leaderboard"
    SHARE_PROGRESS = "share_progress"
    DELETE_LAST_ENTRY = "delete_last_entry"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    UNKNOWN = "unknown"


# Checked in this order - longer/more specific phrases before the short
# confirm/cancel words, so e.g. a steps query never accidentally matches
# CONFIRM just because some unrelated word overlaps.
_INTENT_PRIORITY = [
    Intent.DELETE_LAST_ENTRY,
    Intent.SHARE_PROGRESS,
    Intent.QUERY_LEADERBOARD,
    Intent.QUERY_STREAK,
    Intent.QUERY_STEPS,
    Intent.CONFIRM,
    Intent.CANCEL,
]

KEYWORDS_BY_LANGUAGE: dict[str, dict[Intent, list[str]]] = {
    "en": {
        Intent.QUERY_STEPS: ["how many steps", "my steps", "step count", "steps today"],
        Intent.QUERY_STREAK: ["my streak", "current streak", "how many days streak"],
        Intent.QUERY_LEADERBOARD: ["leaderboard", "my rank", "my position", "where am i ranked"],
        Intent.SHARE_PROGRESS: ["share my progress", "share progress", "post my progress"],
        Intent.DELETE_LAST_ENTRY: [
            "delete my last entry",
            "delete last entry",
            "remove last entry",
            "delete the last entry",
        ],
        Intent.CONFIRM: ["yes", "confirm", "yes confirm", "yes reset"],
        Intent.CANCEL: ["no", "cancel", "never mind", "stop"],
    },
    "yo": {
        Intent.QUERY_STEPS: ["igbesẹ mi", "elo ni igbesẹ mi", "melo ni mo ti rin"],
        Intent.QUERY_STREAK: ["ọjọ́ mi", "elo ọjọ́ ni mo ti rin télé"],
        Intent.QUERY_LEADERBOARD: ["ipo mi", "ipo mi nínú àdíje"],
        Intent.SHARE_PROGRESS: ["pin ilọsiwaju mi", "fi ilọsiwaju mi han"],
        Intent.DELETE_LAST_ENTRY: ["pa igbesẹ tó kẹ́yìn rẹ́", "yọ igbesẹ tó kẹ́yìn kúrò"],
        Intent.CONFIRM: ["bẹ́ẹ̀ni", "mo gbà", "bẹ́ẹ̀ni mo gbà"],
        Intent.CANCEL: ["rárá", "fagilé"],
    },
    "ig": {
        Intent.QUERY_STEPS: ["nzọụkwụ m", "ole nzọụkwụ m", "ole ka nzọụkwụ m dị"],
        Intent.QUERY_STREAK: ["usoro ụbọchị m", "ụbọchị m"],
        Intent.QUERY_LEADERBOARD: ["ọnọdụ m"],
        Intent.SHARE_PROGRESS: ["kesaa ọganihu m"],
        Intent.DELETE_LAST_ENTRY: ["hichapụ ndenye ikpeazụ m", "wepụ ndenye ikpeazụ m"],
        Intent.CONFIRM: ["ee", "kwado"],
        Intent.CANCEL: ["mba", "kagbuo"],
    },
    "ha": {
        # "matakai na" included alongside "matakaina": observed live against
        # real Google STT output that it sometimes splits the compound word
        # into two tokens - matching needs to tolerate that, not just the
        # dictionary-correct spelling.
        Intent.QUERY_STEPS: ["matakaina", "matakai na", "nawa matakaina ne"],
        Intent.QUERY_STREAK: ["jerina", "kwanakina a jere"],
        Intent.QUERY_LEADERBOARD: ["matsayina"],
        Intent.SHARE_PROGRESS: ["raba ci gabana"],
        Intent.DELETE_LAST_ENTRY: ["share shigarwa ta karshe", "goge shigarwa ta karshe"],
        Intent.CONFIRM: ["i", "eh", "tabbatar"],
        Intent.CANCEL: ["a'a", "soke"],
    },
    "pcm": {
        Intent.QUERY_STEPS: ["how many step i waka", "wetin be my steps", "how my steps be"],
        Intent.QUERY_STREAK: ["wetin be my streak", "how many days i don waka"],
        Intent.QUERY_LEADERBOARD: ["wetin be my rank", "where i dey for leaderboard"],
        Intent.SHARE_PROGRESS: ["share my progress", "post my progress"],
        Intent.DELETE_LAST_ENTRY: ["delete my last entry", "remove the last one i enter"],
        Intent.CONFIRM: ["yes", "na so", "i confam"],
        Intent.CANCEL: ["no", "abeg no", "make e stop"],
    },
}


def _normalize(text: str) -> str:
    # Strip diacritics for matching purposes only (the keyword lists above
    # are still written with tone marks for readability/documentation) so
    # transcripts that drop tone marks - common in ASR output - still match.
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def match_intent(transcript: str, language: str) -> Intent:
    normalized = _normalize(transcript)
    if not normalized:
        return Intent.UNKNOWN

    keywords = KEYWORDS_BY_LANGUAGE.get(language, KEYWORDS_BY_LANGUAGE["en"])

    for intent in _INTENT_PRIORITY:
        for phrase in keywords.get(intent, []):
            # Word-boundary match, not raw substring: short confirm/cancel
            # words (e.g. Hausa "i" for yes) would otherwise false-positive
            # inside unrelated words (e.g. matching "i" inside "shi").
            pattern = r"\b" + re.escape(_normalize(phrase)) + r"\b"
            if re.search(pattern, normalized):
                return intent

    return Intent.UNKNOWN
