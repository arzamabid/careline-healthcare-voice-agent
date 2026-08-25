from agent.policies.loader import load_sops


def test_sop_configuration_loads() -> None:
    config = load_sops()

    assert config.version == "1.0"
    assert len(config.sops) == 10


def test_all_expected_sop_ids_exist() -> None:
    config = load_sops()

    ids = {sop.id for sop in config.sops}

    assert ids == {
        "SOP-01",
        "SOP-02",
        "SOP-03",
        "SOP-04",
        "SOP-05",
        "SOP-06",
        "SOP-07",
        "SOP-08",
        "SOP-09",
        "SOP-10",
    }


def test_identity_verification_policy() -> None:
    config = load_sops()

    identity = next(
        sop for sop in config.sops if sop.id == "SOP-01"
    )

    assert identity.rules["minimum_identifiers"] == 2
    assert identity.rules["maximum_failed_attempts"] == 3
    assert identity.rules["patient_data_requires_verification"] is True


def test_appointment_confirmation_policy() -> None:
    config = load_sops()

    appointments = next(
        sop for sop in config.sops if sop.id == "SOP-03"
    )

    assert appointments.rules["explicit_confirmation_required"] is True
    assert (
        appointments.rules[
            "confirmation_required_immediately_before_write"
        ]
        is True
    )
    assert (
        appointments.rules[
            "require_tool_success_before_claiming_success"
        ]
        is True
    )


def test_clinical_advice_is_not_allowed() -> None:
    config = load_sops()

    clinical = next(
        sop for sop in config.sops if sop.id == "SOP-05"
    )

    assert clinical.rules["diagnosis_allowed"] is False
    assert clinical.rules["treatment_recommendation_allowed"] is False
    assert clinical.rules["medication_dosing_allowed"] is False
    assert clinical.rules["clinical_interpretation_allowed"] is False
    assert clinical.rules["escalation_required"] is True
