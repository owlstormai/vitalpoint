from rrb.archetypes import ARCHETYPES, DRIVERS


def test_twelve_archetypes():
    assert len(ARCHETYPES) == 12


def test_archetype_shape():
    for key, a in ARCHETYPES.items():
        assert a.key == key
        assert a.risk in {"low", "medium", "high"}
        assert a.satisfaction in {"frustrated", "neutral", "happy"}
        assert set(a.drivers) <= set(DRIVERS)
        assert len(a.ticket_arcs) >= 2
        assert len(a.qbr_paragraphs) >= 2
        assert a.clause
        assert a.weight >= 1
        assert 0.3 <= a.usage_trend <= 1.3


def test_driver_archetypes_have_marker_arcs():
    # every driver an archetype claims must have a ticket arc or QBR paragraph
    # tagged with that driver so the generator can record evidence doc ids
    for a in ARCHETYPES.values():
        tagged = {d for d, _, _ in a.ticket_arcs} | {d for d, _ in a.qbr_paragraphs}
        for d in a.drivers:
            assert d in tagged, f"{a.key} missing evidence fragment for {d}"
