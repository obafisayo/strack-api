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
        Intent.QUERY_STEPS: [
            "how many steps", "my steps", "step count", "steps today",
            "steps", "how far", "how far have i walked", "how far did i walk",
            "how much have i walked", "show my steps", "check my steps",
            "what are my steps", "steps so far", "daily steps", "show steps",
            "how am i doing", "my progress today", "my activity",
            "how much did i walk", "check my progress", "steps walked",
            "track my steps", "my walk today", "walked today",
        ],
        Intent.QUERY_STREAK: [
            "my streak", "current streak", "how many days streak",
            "streak", "days in a row", "consecutive days", "my streak count",
            "how long is my streak", "what is my streak", "check streak",
            "my current streak", "how many days",
        ],
        Intent.QUERY_LEADERBOARD: [
            "leaderboard", "my rank", "my position", "where am i ranked",
            "ranking", "standings", "how do i compare", "where do i stand",
            "my place", "top scores", "who is winning", "check leaderboard",
            "show leaderboard", "my ranking", "what position",
        ],
        Intent.SHARE_PROGRESS: [
            "share my progress", "share progress", "post my progress",
            "share my steps", "post update", "share to community",
            "tell everyone my progress", "share with everyone",
            "broadcast my progress", "post my steps",
        ],
        Intent.DELETE_LAST_ENTRY: [
            "delete my last entry", "delete last entry", "remove last entry",
            "delete the last entry", "undo my last entry", "remove my last entry",
            "delete last step", "remove last step", "undo last step",
            "delete that", "delete it", "remove that", "undo that",
            "delete the last one", "remove the last one",
        ],
        Intent.CONFIRM: [
            "yes", "confirm", "yes confirm", "yes reset",
            "ok", "okay", "sure", "do it", "go ahead", "yep", "yeah",
            "of course", "absolutely", "correct", "yes please",
            "go for it", "i confirm", "please do",
        ],
        Intent.CANCEL: [
            "no", "cancel", "never mind", "stop",
            "abort", "quit", "nope", "nah", "no thank you",
            "cancel it", "forget it", "i changed my mind",
            "no don't",
        ],
    },
    "yo": {
        # Google STT for Yoruba often drops or simplifies tone marks, and may
        # produce varied word orders. Keywords here cover the most natural
        # phrasings a real user would say, at multiple levels of specificity.
        # Single-word anchors (e.g. "igbesẹ") catch partial STT transcripts
        # that would otherwise always fall through to UNKNOWN.
        Intent.QUERY_STEPS: [
            # multi-word phrases (checked first for specificity)
            "elo ni igbesẹ mi", "melo ni igbesẹ mi", "kini igbesẹ mi",
            "igbesẹ mi loni", "elo igbesẹ mi", "igbesẹ mi bawo ni",
            "melo ni mo ti rin", "elo ni mo ti rin",
            "irin ajo mi", "igbesẹ mi",
            # single-word anchors (broad but necessary for noisy STT output)
            "igbesẹ", "igbese",
        ],
        Intent.QUERY_STREAK: [
            "ọjọ melo ni mo ti rin", "elo ọjọ ni mo ti rin",
            "ọjọ mi", "ọwọọwọ mi", "ọjọ ọwọọwọ mi",
            "melo ni ọjọ mi", "ọjọ to ku", "ọjọ rin mi",
            "streak mi",
        ],
        Intent.QUERY_LEADERBOARD: [
            "ipo mi ninu adije", "ipo mi", "ibo ni mo wa",
            "ibo ni mo duro", "ipele mi", "adije",
        ],
        Intent.SHARE_PROGRESS: [
            "pin ilọsiwaju mi", "fi ilọsiwaju mi han",
            "sọ fun gbogbo eniyan", "pin irin ajo mi",
            "share ilọsiwaju mi",
        ],
        Intent.DELETE_LAST_ENTRY: [
            "pa igbesẹ to kẹyìn rẹ", "yọ igbesẹ to kẹyìn kuro",
            "pa ẹbẹ mi to kẹyìn", "yọ ẹbẹ mi to kẹyìn",
            "pa ẹbẹ naa", "yọ ẹbẹ naa",
        ],
        Intent.CONFIRM: ["bẹẹni", "mo gbà", "bẹẹni mo gbà", "otitọ", "daju"],
        Intent.CANCEL: ["rara", "fagilé", "maṣe", "gba silẹ"],
    },
    "ig": {
        # Same strategy as "yo": multi-word phrases first for specificity,
        # single-word anchors at the end to catch partial/noisy STT output.
        Intent.QUERY_STEPS: [
            "ole nzọụkwụ m dị", "ole nzọụkwụ m", "gwa m nzọụkwụ m",
            "lelee nzọụkwụ m", "ọ bụ ole nzọụkwụ m",
            "nzọụkwụ m taa", "nzọụkwụ m",
            "nzọụkwụ",
        ],
        Intent.QUERY_STREAK: [
            "usoro ụbọchị m ole", "usoro ụbọchị m", "ole ụbọchị m",
            "ụbọchị ole m ji aga", "ọ bụ ole ụbọchị",
            "usoro ụbọchị", "usoro",
        ],
        Intent.QUERY_LEADERBOARD: [
            "ọnọdụ m n'egwuregwu", "ọnọdụ m n'asọmpi", "ọnọdụ m",
            "ebe m nọ", "ole m nọ", "ọnọdụ",
        ],
        Intent.SHARE_PROGRESS: [
            "kesaa ọganihu m", "gosi ọganihu m", "kọọ ndị ọzọ ọganihu m",
            "kesaa", "ọganihu m",
        ],
        Intent.DELETE_LAST_ENTRY: [
            "hichapụ ndenye ikpeazụ m", "wepụ ndenye ikpeazụ m",
            "hichapụ ndenye", "wepụ ndenye",
            "hichapụ ya", "wepụ ya",
        ],
        Intent.CONFIRM: ["ọ dị mma", "kwado ya", "ee kwado", "ee"],
        Intent.CANCEL: ["mba biko", "kagbuo ya", "kagbuo", "mba"],
    },
    "ha": {
        # "matakai na" included alongside "matakaina": observed live against
        # real Google STT output that it sometimes splits the compound word
        # into two tokens - matching needs to tolerate that, not just the
        # dictionary-correct spelling.
        Intent.QUERY_STEPS: [
            "nawa matakaina ne", "yaya matakaina", "gaya mani matakaina",
            "nawa matakai na", "matakai nawa", "matakaina nawa",
            "matakai na", "matakaina",
            "matakai",
        ],
        Intent.QUERY_STREAK: [
            "jerin kwanaki nawa", "kwanaki nawa na jere", "kwanakina a jere",
            "yaya jerin kwanakina", "jerin kwanaki na",
            "jerin kwanaki", "jerina",
            "jerin",
        ],
        Intent.QUERY_LEADERBOARD: [
            "ina na tsaya a jerin", "matsayi na a jerin",
            "ina na tsaya", "matsayi nawa", "matsayina",
            "matsayi",
        ],
        Intent.SHARE_PROGRESS: [
            "raba ci gabana", "nuna wa mutane ci gabana",
            "raba ci gaba", "raba",
        ],
        Intent.DELETE_LAST_ENTRY: [
            "goge shigarwa ta karshe", "share shigarwa ta karshe",
            "goge shigarwa", "share shigarwa",
            "goge ta karshe", "share ta karshe",
        ],
        Intent.CONFIRM: ["tabbatar da shi", "i tabbatar", "tabbatar", "eh", "i"],
        Intent.CANCEL: ["a'a bari", "soke shi", "soke", "a'a"],
    },
    "pcm": {
        # Pidgin borrows heavily from English. Single-word English anchors
        # ("steps", "streak", "rank") are listed explicitly here because
        # this list is only consulted when language == "pcm", not "en".
        Intent.QUERY_STEPS: [
            "how many step i waka", "how far i don waka", "wetin be my steps",
            "how my steps be", "show me my steps", "check my steps",
            "how many i waka", "my waka today",
            "my steps", "how many steps",
            "waka", "steps",
        ],
        Intent.QUERY_STREAK: [
            "how many days i don waka", "how long my streak don be",
            "wetin be my streak", "my streak na wetin",
            "how many days", "my streak",
            "streak",
        ],
        Intent.QUERY_LEADERBOARD: [
            "where i dey for leaderboard", "wetin be my rank",
            "where i dey rank", "my position for leaderboard",
            "my rank", "leaderboard",
            "rank",
        ],
        Intent.SHARE_PROGRESS: [
            "share my progress", "post my progress",
            "tell everybody my progress", "make people know my progress",
            "broadcast my progress", "share am",
        ],
        Intent.DELETE_LAST_ENTRY: [
            "delete my last entry", "remove the last one i enter",
            "delete the last one", "remove my last entry",
            "delete am", "remove am", "wipe am",
        ],
        Intent.CONFIRM: ["i confam", "na so", "do am", "go ahead", "correct", "yes"],
        Intent.CANCEL: ["abeg no", "no abeg", "make e stop", "cancel am", "stop am", "no"],
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
