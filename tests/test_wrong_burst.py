"""Wrong-answer toast matches the correct-answer burst."""

from baton_relay.ui.correct_burst import WrongBurst
from baton_relay.ui.main_window import _points_caption


def test_points_caption():
    assert _points_caption(5) == "+5 pts"
    assert _points_caption(2.5) == "+2.5 pts"
    assert _points_caption(0) == "0 pts"
    assert _points_caption(-1) == "-1 pts"


def test_wrong_burst_titles(qtbot):
    burst = WrongBurst()
    qtbot.addWidget(burst)
    burst.resize(800, 600)

    burst.play("0 pts", fade_in_ms=0, hold_ms=5000, fade_out_ms=0)
    qtbot.wait(20)
    assert burst.label.text() == "WRONG"
    assert burst.sub.text() == "0 pts"
    assert burst.card.objectName() == "wrongToast"
    assert burst.isVisible()

    burst.play("+2 pts", partial=True, fade_in_ms=0, hold_ms=5000, fade_out_ms=0)
    qtbot.wait(20)
    assert burst.label.text() == "PARTIAL"
    assert burst.sub.text() == "+2 pts"
    assert burst.card.objectName() == "partialToast"
    assert burst.isVisible()
