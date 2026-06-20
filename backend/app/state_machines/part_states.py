"""Part state machine for managing part lifecycle."""

from enum import Enum


class PartState(str, Enum):
    """Part states."""

    DRAFT = "draft"  # Initial draft
    PENDING_QUOTE = "pending_quote"  # Waiting for quote approval
    QUOTED = "quoted"  # Quote approved
    SAMPLING = "sampling"  # In sampling phase
    SAMPLE_APPROVED = "sample_approved"  # Sample approved
    MASS_PRODUCTION = "mass_production"  # In mass production
    EOL = "eol"  # End of life
    OBSOLETE = "obsolete"  # Part is obsolete


class PartTransition(str, Enum):
    """Part state transitions."""

    SUBMIT_QUOTE = "submit_quote"  # Draft -> PendingQuote
    APPROVE_QUOTE = "approve_quote"  # PendingQuote -> Quoted
    REJECT_QUOTE = "reject_quote"  # PendingQuote -> Draft
    START_SAMPLE = "start_sample"  # Quoted -> Sampling
    APPROVE_SAMPLE = "approve_sample"  # Sampling -> SampleApproved
    REJECT_SAMPLE = "reject_sample"  # Sampling -> Draft
    START_MASS = "start_mass"  # SampleApproved -> MassProduction
    END_LIFE = "end_life"  # MassProduction -> EOL
    OBSOLETE = "obsolete"  # Any state -> Obsolete
    REVIVE = "revive"  # EOL/Obsolete -> MassProduction


# State transition map
PART_TRANSITIONS: dict[PartState, dict[PartTransition, PartState]] = {
    PartState.DRAFT: {
        PartTransition.SUBMIT_QUOTE: PartState.PENDING_QUOTE,
    },
    PartState.PENDING_QUOTE: {
        PartTransition.APPROVE_QUOTE: PartState.QUOTED,
        PartTransition.REJECT_QUOTE: PartState.DRAFT,
    },
    PartState.QUOTED: {
        PartTransition.START_SAMPLE: PartState.SAMPLING,
    },
    PartState.SAMPLING: {
        PartTransition.APPROVE_SAMPLE: PartState.SAMPLE_APPROVED,
        PartTransition.REJECT_SAMPLE: PartState.DRAFT,
    },
    PartState.SAMPLE_APPROVED: {
        PartTransition.START_MASS: PartState.MASS_PRODUCTION,
    },
    PartState.MASS_PRODUCTION: {
        PartTransition.END_LIFE: PartState.EOL,
        PartTransition.OBSOLETE: PartState.OBSOLETE,
    },
    PartState.EOL: {
        PartTransition.REVIVE: PartState.MASS_PRODUCTION,
    },
    PartState.OBSOLETE: {
        PartTransition.REVIVE: PartState.MASS_PRODUCTION,
    },
}


class PartStateMachine:
    """State machine for part lifecycle."""

    def __init__(self, current_state: PartState):
        self.current_state = current_state

    def can_transition(self, transition: PartTransition) -> bool:
        """Check if transition is valid."""
        transitions = PART_TRANSITIONS.get(self.current_state, {})
        return transition in transitions

    def transition(self, transition: PartTransition) -> PartState:
        """Execute a state transition."""
        if not self.can_transition(transition):
            raise ValueError(
                f"Cannot perform {transition.value} from {self.current_state.value}"
            )

        transitions = PART_TRANSITIONS[self.current_state]
        self.current_state = transitions[transition]
        return self.current_state

    def get_available_transitions(self) -> list[PartTransition]:
        """Get all valid transitions from current state."""
        transitions = PART_TRANSITIONS.get(self.current_state, {})
        return list(transitions.keys())

    def is_production_ready(self) -> bool:
        """Check if part can go to mass production."""
        return self.current_state == PartState.SAMPLE_APPROVED


def get_part_path(current_state: PartState) -> str:
    """Get the business path for a part based on state."""
    if current_state == PartState.DRAFT:
        return "draft"
    elif current_state in (PartState.PENDING_QUOTE, PartState.QUOTED):
        return "quote"
    elif current_state in (PartState.SAMPLING, PartState.SAMPLE_APPROVED):
        return "sample"
    elif current_state == PartState.MASS_PRODUCTION:
        return "mass"
    else:
        return "inactive"
