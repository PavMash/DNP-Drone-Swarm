from enum import Enum, auto

class MessageType(Enum):
    # --- Simulation control ---
    START = auto()
    STOP = auto()
    TICK = auto()

    # --- Drone ↔ Environment ---
    REGISTER = auto()
    UPDATE_POSITION = auto()
    SEND_LOCAL = auto()

    # --- Environment → Drone ---
    DELIVER = auto()

    # --- Swarm / Gossip layer ---
    LEADER = auto()