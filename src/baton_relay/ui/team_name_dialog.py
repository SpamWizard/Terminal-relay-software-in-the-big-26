"""Popup when a team name was already used."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from baton_relay.results.log import PriorTeamRun


class TeamNameConflictDialog(QDialog):
    """WOAH — name already taken. Resume unfinished run, or change the name."""

    RESUME = 1
    CHANGE = 2

    def __init__(
        self,
        team_name: str,
        *,
        resumable: PriorTeamRun | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Team name taken")
        self.setModal(True)
        self._choice = self.CHANGE

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        whoa = QLabel("WOAH — are you sure?")
        whoa.setObjectName("headline")
        whoa.setAlignment(Qt.AlignmentFlag.AlignCenter)
        whoa.setWordWrap(True)
        root.addWidget(whoa)

        body = QLabel(f'There\'s already a team called "{team_name}".')
        body.setObjectName("muted")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        root.addWidget(body)

        if resumable is not None:
            detail = QLabel(
                "That team didn't finish. Resume their run, or pick a different name."
            )
            if resumable.roster_names:
                crew = ", ".join(resumable.roster_names)
                detail.setText(
                    f"That team didn't finish ({crew}). "
                    "Resume their run, or pick a different name."
                )
            detail.setObjectName("muted")
            detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            detail.setWordWrap(True)
            root.addWidget(detail)

            buttons = QDialogButtonBox()
            resume_btn = QPushButton("RESUME")
            resume_btn.setObjectName("primary")
            change_btn = QPushButton("CHANGE NAME")
            change_btn.setObjectName("ghost")
            buttons.addButton(resume_btn, QDialogButtonBox.ButtonRole.AcceptRole)
            buttons.addButton(change_btn, QDialogButtonBox.ButtonRole.RejectRole)
            resume_btn.clicked.connect(self._pick_resume)
            change_btn.clicked.connect(self._pick_change)
            root.addWidget(buttons)
        else:
            detail = QLabel("Pick a different team name — no duplicates, no #1 / #2 suffixes.")
            detail.setObjectName("muted")
            detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            detail.setWordWrap(True)
            root.addWidget(detail)

            buttons = QDialogButtonBox()
            change_btn = QPushButton("CHANGE NAME")
            change_btn.setObjectName("primary")
            buttons.addButton(change_btn, QDialogButtonBox.ButtonRole.AcceptRole)
            change_btn.clicked.connect(self._pick_change)
            root.addWidget(buttons)

        self.setMinimumWidth(420)

    def _pick_resume(self) -> None:
        self._choice = self.RESUME
        self.accept()

    def _pick_change(self) -> None:
        self._choice = self.CHANGE
        self.accept()

    @property
    def choice(self) -> int:
        return self._choice
