"""Machine state machine for managing equipment/machine lifecycle."""

from enum import Enum


class MachineState(str, Enum):
    """Machine states."""

    IDLE = "idle"  # Available and idle
    RUNNING = "running"  # Currently in production
    MAINTENANCE = "maintenance"  # Under maintenance
    REPAIR = "repair"  # Under repair
    BROKEN = "broken"  # Broken down
    STANDBY = "standby"  # Standby/ready
    RETIRED = "retired"  # Retired from service


class MachineTransition(str, Enum):
    """Machine state transitions."""

    START = "start"  # Idle -> Running
    STOP = "stop"  # Running -> Idle
    PAUSE = "pause"  # Running -> Standby
    RESUME = "resume"  # Standby -> Running
    SCHEDULE_MAINTENANCE = "schedule_maintenance"  # Idle -> Maintenance
    COMPLETE_MAINTENANCE = "complete_maintenance"  # Maintenance -> Idle
    REPORT_BREAKDOWN = "report_breakdown"  # Running -> Broken
    START_REPAIR = "start_repair"  # Broken -> Repair
    COMPLETE_REPAIR = "complete_repair"  # Repair -> Idle
    RETIRE = "retire"  # Any state -> Retired


# State transition map
MACHINE_TRANSITIONS: dict[MachineState, dict[MachineTransition, MachineState]] = {
    MachineState.IDLE: {
        MachineTransition.START: MachineState.RUNNING,
        MachineTransition.SCHEDULE_MAINTENANCE: MachineState.MAINTENANCE,
        MachineTransition.REPORT_BREAKDOWN: MachineState.BROKEN,
        MachineTransition.RETIRE: MachineState.RETIRED,
    },
    MachineState.RUNNING: {
        MachineTransition.STOP: MachineState.IDLE,
        MachineTransition.PAUSE: MachineState.STANDBY,
        MachineTransition.REPORT_BREAKDOWN: MachineState.BROKEN,
        MachineTransition.RETIRE: MachineState.RETIRED,
    },
    MachineState.STANDBY: {
        MachineTransition.RESUME: MachineState.RUNNING,
        MachineTransition.STOP: MachineState.IDLE,
        MachineTransition.REPORT_BREAKDOWN: MachineState.BROKEN,
    },
    MachineState.MAINTENANCE: {
        MachineTransition.COMPLETE_MAINTENANCE: MachineState.IDLE,
        MachineTransition.REPORT_BREAKDOWN: MachineState.BROKEN,
    },
    MachineState.REPAIR: {
        MachineTransition.COMPLETE_REPAIR: MachineState.IDLE,
    },
    MachineState.BROKEN: {
        MachineTransition.START_REPAIR: MachineState.REPAIR,
        MachineTransition.RETIRE: MachineState.RETIRED,
    },
    MachineState.RETIRED: {},  # Terminal state
}


class MachineStateMachine:
    """State machine for machine/equipment lifecycle."""

    def __init__(self, current_state: MachineState):
        self.current_state = current_state

    def can_transition(self, transition: MachineTransition) -> bool:
        """Check if transition is valid."""
        transitions = MACHINE_TRANSITIONS.get(self.current_state, {})
        return transition in transitions

    def transition(self, transition: MachineTransition) -> MachineState:
        """Execute a state transition."""
        if not self.can_transition(transition):
            raise ValueError(
                f"Cannot perform {transition.value} from {self.current_state.value}"
            )

        transitions = MACHINE_TRANSITIONS[self.current_state]
        self.current_state = transitions[transition]
        return self.current_state

    def get_available_transitions(self) -> list[MachineTransition]:
        """Get all valid transitions from current state."""
        transitions = MACHINE_TRANSITIONS.get(self.current_state, {})
        return list(transitions.keys())

    def is_available(self) -> bool:
        """Check if machine is available for production."""
        return self.current_state in (MachineState.IDLE, MachineState.STANDBY)

    def is_producing(self) -> bool:
        """Check if machine is currently producing."""
        return self.current_state == MachineState.RUNNING


def get_machine_status_category(state: MachineState) -> str:
    """Get status category for dashboard display."""
    if state in (MachineState.IDLE, MachineState.STANDBY):
        return "available"
    elif state == MachineState.RUNNING:
        return "producing"
    elif state in (MachineState.MAINTENANCE, MachineState.REPAIR):
        return "maintenance"
    elif state == MachineState.BROKEN:
        return "down"
    else:
        return "inactive"
