"""Localized response templates for spoken voice replies.

This exists because TTS pronunciation correctness depends on it directly:
YarnGPT synthesizes whatever characters it's given, so a reply generated in
English and read by a Yoruba/Igbo/Hausa voice produces a voice with the
right accent reading the wrong language entirely. Every spoken reply must be
built from a template in the requested language, not just routed to a voice
that matches it.

Tone marks (Yoruba àmìohùn, Igbo akara edemede) are not cosmetic here - these
are tonal languages where the marks change which word is actually being
said, and that distinction is exactly what determines whether YarnGPT
pronounces the intended word. Every Yoruba/Igbo/Hausa template below is
written with full diacritics for that reason.

CAVEAT: same honesty as voice_intent_service.py's keyword dictionary - these
are my best-effort translations, not reviewed by a native speaker of any of
these languages. Tone-mark errors here are a pronunciation bug, not just a
typo - get native speaker review before relying on this in production.
"""

_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "steps_remaining": (
            "You've completed {steps} steps today. "
            "You have {remaining} steps remaining to reach today's goal."
        ),
        "steps_goal_reached": "You've completed {steps} steps today. You've already reached today's goal!",
        "streak_active": "You're on a {days}-day streak. Keep it up!",
        "streak_none": "You don't have an active streak yet - complete today's goal to start one.",
        "leaderboard_ranked": "You're ranked number {rank} on today's leaderboard.",
        "leaderboard_unranked": "You're not on today's leaderboard yet.",
        "progress_shared": "Your progress has been shared to the community feed.",
        "delete_confirm_prompt": (
            "Are you sure you want to delete your last entry of {steps} steps? "
            "Say yes to confirm, or no to cancel."
        ),
        "delete_confirmed": "Deleted your last entry of {steps} steps.",
        "no_entries_to_delete": "You don't have any step entries to delete.",
        "nothing_pending": "There's nothing waiting for confirmation.",
        "entry_gone": "That entry no longer exists.",
        "confirm_failed": "Sorry, I couldn't process that confirmation.",
        "nothing_to_cancel": "There's nothing to cancel.",
        "cancelled": "Okay, cancelled.",
        "unknown_intent": "Sorry, I didn't understand that. Please try again.",
        "briefing_streak": "You're on a {days}-day streak.",
        "welcome": "Welcome to Strack. Cheers to a great start today!",
        "keep_going": "Keep it up! You're doing great today.",
    },
    "yo": {
        "steps_remaining": (
            "O ti rìn ìgbésẹ̀ {steps} lónìí. Ìgbésẹ̀ {remaining} ló kù fún ọ "
            "láti dé góòlù òní."
        ),
        "steps_goal_reached": "O ti rìn ìgbésẹ̀ {steps} lónìí. O ti dé góòlù òní! Ẹ kú iṣẹ́ rere.",
        "streak_active": "O wà lórí ọjọ́ {days} ní ọ̀wọ́ọ̀wọ́. Ẹ máa báa lọ!",
        "streak_none": "O kò tíì ní ọ̀wọ́ ọjọ́ kankan - parí góòlù òní láti bẹ̀rẹ̀ ọ̀kan.",
        "leaderboard_ranked": "O wà ní ipò {rank} nínú àtòjọ àwọn olórí òní.",
        "leaderboard_unranked": "O kò tíì sí nínú àtòjọ àwọn olórí òní.",
        "progress_shared": "A ti fi ìlọsíwájú rẹ hàn nínú ẹ̀rọ àjọṣepọ̀.",
        "delete_confirm_prompt": (
            "Ṣé o dá ọ́ lójú pé o fẹ́ pa ìgbésẹ̀ tó kẹ́yìn rẹ ti ìgbésẹ̀ {steps} rẹ́? "
            "Sọ bẹ́ẹ̀ni láti jẹ́rìí, tàbí rárá láti fagilé."
        ),
        "delete_confirmed": "A ti pa ìgbésẹ̀ tó kẹ́yìn rẹ ti ìgbésẹ̀ {steps} rẹ́.",
        "no_entries_to_delete": "O kò ní ìgbésẹ̀ kankan láti pa rẹ́.",
        "nothing_pending": "Kò sí ohun kankan tó ń dúró de ìjẹ́rìí.",
        "entry_gone": "Ìgbésẹ̀ yẹn kò sí mọ́.",
        "confirm_failed": "Má bínú, n kò lè ṣe ìjẹ́rìí yẹn.",
        "nothing_to_cancel": "Kò sí ohun kankan láti fagilé.",
        "cancelled": "Ó dára, ó ti fagilé.",
        "unknown_intent": "Má bínú, n kò gbọ́ ohun tí o sọ. Jọ̀wọ́ tún sọ.",
        "briefing_streak": "O wà lórí ọjọ́ {days} ní ọ̀wọ́ọ̀wọ́.",
        "welcome": "Káàbọ̀ sí Strack. Ẹ kú ìbẹ̀rẹ̀ rere lónìí!",
        "keep_going": "Ẹ máa báa lọ! O ń ṣe dáadáa lónìí.",
    },
    "ig": {
        "steps_remaining": (
            "Ị zọọla nzọụkwụ {steps} taa. Nzọụkwụ {remaining} ka fọdụrụ "
            "iji rute ebumnuche taa."
        ),
        "steps_goal_reached": "Ị zọọla nzọụkwụ {steps} taa. Ị rutela ebumnuche taa! Ọ dị mma.",
        "streak_active": "Ị nọ na usoro ụbọchị {days}. Gaa n'ihu!",
        "streak_none": "Ị nweghị usoro ụbọchị ugbu a - mezuo ebumnuche taa iji malite otu.",
        "leaderboard_ranked": "Ị nọ n'ọnọdụ {rank} na ndepụta ndị isi taa.",
        "leaderboard_unranked": "Ị anọghị na ndepụta ndị isi taa.",
        "progress_shared": "Ekesaala ọganihu gị na ngwa ọha mmadụ.",
        "delete_confirm_prompt": (
            "Ị ji n'aka na ị chọrọ ihichapụ ndenye ikpeazụ gị nke nzọụkwụ {steps}? "
            "Kwuo ee iji kwado, ma ọ bụ mba iji kagbuo."
        ),
        "delete_confirmed": "Ehichapụla ndenye ikpeazụ gị nke nzọụkwụ {steps}.",
        "no_entries_to_delete": "Ị nweghị ndenye nzọụkwụ ọ bụla iji hichapụ.",
        "nothing_pending": "Ọ dịghị ihe na-eche nkwado.",
        "entry_gone": "Ndenye ahụ adịghịzi.",
        "confirm_failed": "Ndo, enweghị m ike ịhazi nkwado ahụ.",
        "nothing_to_cancel": "Ọ dịghị ihe ị ga-akagbu.",
        "cancelled": "Ọ dị mma, akagbuola ya.",
        "unknown_intent": "Ndo, aghọtaghị m ihe ị kwuru. Biko gwa ọzọ.",
        "briefing_streak": "Ị nọ na usoro ụbọchị {days}.",
        "welcome": "Nnọọ na Strack. Ka taa bụrụ mmalite ọma!",
        "keep_going": "Gaa n'ihu! Ị na-eme nke ọma taa.",
    },
    "ha": {
        "steps_remaining": (
            "Ka kammala matakai {steps} a yau. Matakai {remaining} sun rage "
            "don kai burin yau."
        ),
        "steps_goal_reached": "Ka kammala matakai {steps} a yau. Ka riga ka kai burin yau! Madalla.",
        "streak_active": "Kana kan jerin kwanaki {days} a jere. Ci gaba da haka!",
        "streak_none": "Ba ka da jerin kwanaki yanzu - kammala burin yau don fara ɗaya.",
        "leaderboard_ranked": "Kana matsayi na {rank} a jerin manyan yau.",
        "leaderboard_unranked": "Ba ka cikin jerin manyan yau ba tukuna.",
        "progress_shared": "An raba ci gabanka zuwa ga al'umma.",
        "delete_confirm_prompt": (
            "Ka tabbata kana son share shigarwa ta karshe ta matakai {steps}? "
            "Ka ce i don tabbatarwa, ko a'a don sokewa."
        ),
        "delete_confirmed": "An share shigarwa ta karshe ta matakai {steps}.",
        "no_entries_to_delete": "Ba ka da wata shigarwar matakai don sharewa.",
        "nothing_pending": "Babu wani abu da ke jiran tabbatarwa.",
        "entry_gone": "Wannan shigarwar ba ta wanzu kuma.",
        "confirm_failed": "Yi haƙuri, ban iya sarrafa wannan tabbatarwar ba.",
        "nothing_to_cancel": "Babu abin sokewa.",
        "cancelled": "To, an soke shi.",
        "unknown_intent": "Yi haƙuri, ban fahimci abin da ka faɗa ba. Don Allah a sake faɗi.",
        "briefing_streak": "Kana kan jerin kwanaki {days}.",
        "welcome": "Barka da zuwa Strack. Barka da farawa mai kyau a yau!",
        "keep_going": "Ci gaba da haka! Kana yin kyau a yau.",
    },
    "pcm": {
        "steps_remaining": (
            "You don waka {steps} steps today. {remaining} steps remain "
            "make you reach today goal."
        ),
        "steps_goal_reached": "You don waka {steps} steps today. You don already reach today goal!",
        "streak_active": "You dey on {days}-day streak. Carry go!",
        "streak_none": "You no get active streak yet - complete today goal make you start one.",
        "leaderboard_ranked": "You dey number {rank} for today leaderboard.",
        "leaderboard_unranked": "You never enter today leaderboard.",
        "progress_shared": "Dem don share your progress for di community feed.",
        "delete_confirm_prompt": (
            "You sure say you wan delete your last entry of {steps} steps? "
            "Talk yes make you confirm, or no make you cancel."
        ),
        "delete_confirmed": "We don delete your last entry of {steps} steps.",
        "no_entries_to_delete": "You no get any step entry to delete.",
        "nothing_pending": "Nothing dey wait for confirmation.",
        "entry_gone": "That entry no dey again.",
        "confirm_failed": "Sorry, we no fit process that confirmation.",
        "nothing_to_cancel": "Nothing to cancel.",
        "cancelled": "Ok, e don cancel.",
        "unknown_intent": "Sorry, I no understand wetin you talk. Abeg try again.",
        "briefing_streak": "You dey on {days}-day streak.",
        "welcome": "Welcome to Strack. Cheers to a great start today!",
        "keep_going": "Carry go! You dey do well today.",
    },
}


def t(language: str, key: str, **kwargs) -> str:
    """Renders the named template in the requested language, falling back to
    English if the language or key isn't covered."""
    templates = _TEMPLATES.get(language, _TEMPLATES["en"])
    template = templates.get(key, _TEMPLATES["en"][key])
    return template.format(**kwargs)
