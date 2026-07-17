from research.scripts.rescore_morph_aware_naturalness import (
    MORPH_ARMS,
    REFERENCE_ARMS,
)


def test_morph_rescore_has_all_eight_required_arms():
    assert len(MORPH_ARMS) == 8
    assert all(item.required for item in MORPH_ARMS)
    assert len({item.arm.key for item in MORPH_ARMS}) == 8
    assert len({item.arm.db_name for item in MORPH_ARMS}) == 8
    assert all(
        item.arm.db_name.startswith("direction_3_smoke5_")
        for item in MORPH_ARMS
    )


def test_direction_1_references_are_optional_and_separate():
    assert REFERENCE_ARMS
    assert all(not item.required for item in REFERENCE_ARMS)
    assert all(
        item.arm.db_name.startswith("direction_1p2_")
        for item in REFERENCE_ARMS
    )
