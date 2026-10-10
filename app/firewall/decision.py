# ============================================================
# FIREWALL DECISION ENGINE
# LLM HALLUCINATION FIREWALL
# ============================================================


class FirewallDecision:

    def __init__(self):
        pass

    def decide(
        self,
        claim_results,
        contradiction_result=None,
        access_denied=False
    ):

        # ----------------------------------------------------
        # ACCESS CONTROL
        # ----------------------------------------------------
        if access_denied:
            return {
                "status": "ACCESS DENIED",
                "reason": (
                    "The required information is not "
                    "available to this user."
                )
            }

        # ----------------------------------------------------
        # NO CLAIMS
        # ----------------------------------------------------
        if not claim_results:
            return {
                "status": "BLOCKED",
                "reason": (
                    "No verifiable claims were found "
                    "in the generated answer."
                )
            }

        # ----------------------------------------------------
        # CONTRADICTION CHECK
        # ----------------------------------------------------
        if contradiction_result:
            if contradiction_result.get(
                "has_conflict",
                False
            ):
                return {
                    "status": "AMBIGUOUS",
                    "reason": (
                        contradiction_result.get(
                            "message"
                        )
                        or
                        "Conflicting evidence was found."
                    )
                }

        # ----------------------------------------------------
        # CLAIM SUPPORT CHECK
        # ----------------------------------------------------
        supported_claims = sum(
            1
            for result in claim_results
            if result.get(
                "supported",
                False
            )
        )

        total_claims = len(
            claim_results
        )

        # ----------------------------------------------------
        # ALL CLAIMS SUPPORTED
        # ----------------------------------------------------
        if supported_claims == total_claims:
            return {
                "status": "VERIFIED",
                "reason": (
                    "All generated claims are "
                    "supported by retrieved evidence."
                )
            }

        # ----------------------------------------------------
        # SOME CLAIMS SUPPORTED
        # ----------------------------------------------------
        if supported_claims > 0:
            return {
                "status": "PARTIALLY VERIFIED",
                "reason": (
                    "Some generated claims are "
                    "supported, but others lack "
                    "sufficient evidence."
                )
            }

        # ----------------------------------------------------
        # NO CLAIMS SUPPORTED
        # ----------------------------------------------------
        return {
            "status": "BLOCKED",
            "reason": (
                "The generated answer could not "
                "be supported by the available evidence."
            )
        }


def create_firewall_decision():
    return FirewallDecision()