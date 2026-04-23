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
    DELIVER = auto()

    # --- Swarm / Gossip layer ---
    LEADER = auto()


# --- Description of message types ---

# START: Start the simulation (sent to environment from main.py)
# Structure: {"type": MessageType.START}

# STOP: Stop the simulation (sent to environment from main.py)
# Structure: {"type": MessageType.STOP}

# TICK: Start new tick in simultaion inside environment and notify drones of a new tick
# (sent to environment from environtment itself and from environment to drones)
# Structure: {"type": MessageType.TICK} - when sent to environment
#            {"type": MessageType.TICK, "tick": current_tick} - when sent to drones

# REGISTER: Register new drone in environment (sent to environment from main.py)
# Structure: {"type": MessageType.REGISTER, "drone": actor_ref, "position": (x, y)}

# UPDATE_POSITION: Update drone position in environment (sent to environment from drones)
# Structure: {"type": MessageType.UPDATE_POSITION, "drone": actor_ref, "position": (x, y)}

# SEND_LOCAL: Send message to all drones within communication radius (sent to environment from drones)
# Structure: {"type": MessageType.SEND_LOCAL, "sender": actor_ref, "payload": {...}}
# - Payload holds a message that will be delivered to nearby drones

# DELIVER: Deliver message to drone (sent to drones from environment)
# Structure: {"type": MessageType.DELIVER, "payload": {...}}

# LEADER: Leader announcement (sent to drones from drones)
# Structure: {"type": MessageType.LEADER, "leader_id": id, "leader_version": version, "tick": tick}
# - Version keeps track of how many times leadership has changed. Higher version = more recent info.
# - Within one version, higher leader_id wins.
# - Tick is the tick when the message was sent by leader or candidate leader. Used to detect leader timeouts.