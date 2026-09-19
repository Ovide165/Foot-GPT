"""
Security & Guardrails Module for foot-GPT.
"""

import re
from typing import Tuple


class SecurityGuardrails:
    """
    Validates query safety, prompt injection resistance, and domain boundaries.
    """

    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"system\s+prompt",
        r"you\s+are\s+now\s+in\s+developer\s+mode",
        r"jailbreak",
        r"dan\s+mode",
        r"reveal\s+your\s+instructions",
    ]

    OUT_OF_SCOPE_PATTERNS = [
        r"recette\s+de\s+cuisine|cooking\s+recipe",
        r"cours\s+de\s+bourse|stock\s+market",
        r"politique\s+présidentielle|presidential\s+election",
        r"bitcoin|cryptocurrency",
        r"écris\s+du\s+code|write\s+c\+\+\s+code",
    ]

    @classmethod
    def sanitize_and_validate(cls, query: str) -> Tuple[bool, str]:
        """
        Validates coach query.
        Returns (is_valid, reason_or_cleaned_query).
        """
        cleaned = query.strip()
        if len(cleaned) < 3:
            return False, "Query is too short to be processed."

        # 1. Anti-Injection Verification
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return False, "Unauthorized query: prompt injection attempt detected."

        # 2. Domain Boundary Verification
        for pattern in cls.OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return False, "Out of domain query: foot-GPT is strictly dedicated to tactical football analysis."

        return True, cleaned
