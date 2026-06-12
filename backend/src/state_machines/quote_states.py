"""Quote state machine for managing quote lifecycle."""

from enum import Enum
from typing import Callable


class QuoteState(str, Enum):
    """Quote states."""

    DRAFT = "draft"  # Initial draft
    TECH_REVIEW = "tech_review"  # Technical review pending
    PENDING_BOSS = "pending_boss"  # Submitted for boss approval
    APPROVED = "approved"  # Boss approved
    REJECTED = "rejected"  # Rejected
    FIXED = "fixed"  # Fixed point confirmed (customer accepted)
    CANCELLED = "cancelled"  # Cancelled


class QuoteTransition(str, Enum):
    """Quote state transitions."""

    SUBMIT_FOR_REVIEW = "submit_for_review"  # Draft -> TechReview
    TECH_APPROVE = "tech_approve"  # TechReview -> PendingBoss
    TECH_REJECT = "tech_reject"  # TechReview -> Rejected
    BOSS_APPROVE = "boss_approve"  # PendingBoss -> Approved
    BOSS_REJECT = "boss_reject"  # PendingBoss -> Rejected
    FIX = "fix"  # Approved -> Fixed
    CANCEL = "cancel"  # Any state except Fixed/Cancelled -> Cancelled
    REVISE = "revise"  # Rejected -> Draft (start over)


# State transition map: current_state -> {transition: next_state}
QUOTE_TRANSITIONS: dict[QuoteState, dict[QuoteTransition, QuoteState]] = {
    QuoteState.DRAFT: {
        QuoteTransition.SUBMIT_FOR_REVIEW: QuoteState.TECH_REVIEW,
        QuoteTransition.CANCEL: QuoteState.CANCELLED,
    },
    QuoteState.TECH_REVIEW: {
        QuoteTransition.TECH_APPROVE: QuoteState.PENDING_BOSS,
        QuoteTransition.TECH_REJECT: QuoteState.REJECTED,
        QuoteTransition.CANCEL: QuoteState.CANCELLED,
    },
    QuoteState.PENDING_BOSS: {
        QuoteTransition.BOSS_APPROVE: QuoteState.APPROVED,
        QuoteTransition.BOSS_REJECT: QuoteState.REJECTED,
        QuoteTransition.CANCEL: QuoteState.CANCELLED,
    },
    QuoteState.APPROVED: {
        QuoteTransition.FIX: QuoteState.FIXED,
        QuoteTransition.CANCEL: QuoteState.CANCELLED,
    },
    QuoteState.REJECTED: {
        QuoteTransition.REVISE: QuoteState.DRAFT,
    },
    QuoteState.FIXED: {},  # Terminal state
    QuoteState.CANCELLED: {},  # Terminal state
}


class QuoteStateMachine:
    """State machine for quote workflow."""

    def __init__(self, current_state: QuoteState):
        self.current_state = current_state

    def can_transition(self, transition: QuoteTransition) -> bool:
        """Check if transition is valid from current state."""
        transitions = QUOTE_TRANSITIONS.get(self.current_state, {})
        return transition in transitions

    def transition(self, transition: QuoteTransition) -> QuoteState:
        """Execute a state transition."""
        if not self.can_transition(transition):
            raise ValueError(
                f"Cannot perform {transition.value} from {self.current_state.value}"
            )

        transitions = QUOTE_TRANSITIONS[self.current_state]
        self.current_state = transitions[transition]
        return self.current_state

    def get_available_transitions(self) -> list[QuoteTransition]:
        """Get all valid transitions from current state."""
        transitions = QUOTE_TRANSITIONS.get(self.current_state, {})
        return list(transitions.keys())

    def is_terminal(self) -> bool:
        """Check if current state is a terminal state."""
        return self.current_state in (QuoteState.FIXED, QuoteState.CANCELLED)


def validate_quote_transition(
    current_state: QuoteState,
    target_state: QuoteState,
) -> bool:
    """Validate if transition between states is allowed."""
    transitions = QUOTE_TRANSITIONS.get(current_state, {})
    return target_state in transitions.values()
