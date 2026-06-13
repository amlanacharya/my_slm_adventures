from __future__ import annotations

from typing import Literal

RouteDecision = Literal["finalize", "revise", "degrade"]


def decide(validation_ok: bool, critic_passed: bool, attempt: int, budget: int) -> RouteDecision:
    if validation_ok and critic_passed:
        return "finalize"
    if attempt >= budget:
        return "degrade"
    return "revise"
