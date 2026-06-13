from specguard.router import decide


def test_decide_finalizes_when_validation_and_critic_pass():
    assert decide(validation_ok=True, critic_passed=True, attempt=1, budget=3) == "finalize"


def test_decide_revises_when_budget_remains():
    assert decide(validation_ok=True, critic_passed=False, attempt=1, budget=3) == "revise"


def test_decide_degrades_when_budget_is_exhausted():
    assert decide(validation_ok=False, critic_passed=False, attempt=3, budget=3) == "degrade"
