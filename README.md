# DNP Drone Swarm

## Model

- The simulation runs on a 2D square field.
- A predefined number of drones is spawned inside this field.
- Every drone has the same fixed communication radius and can exchange messages only with neighbors in range.
- The swarm leader coordinates movement toward the center area of the field.
- If there are no other drones within communication radius of a drone, it considers itself as a swarm leader (swarm of single drone)
- Messages from leader and other drones propagate from neighbors to neighbors eventually covering whole swarm (Gossip algorithm)

## Design decisions and architecture description

### Environment, drones and simulation design 

- All drones and the environment run in a single process as separate threads, which is sufficient for this simulation.
- The project uses the `Pykka` library for drone and environment simulation. Read about Pykka and the actor model in the [official documentation](https://pykka.readthedocs.io/stable/).
    ```
    pip install pykka
    ```
- Both drones and the environment are `Pykka` actors. When drone wants to communicate to other drones, it sends message to environment that checks drone neighborhood and delivers message those who can receive it
- `Drone`, `Environment`, and `main.py` communicate with message types defined in `message_type.py`.
- Simulation time is controlled by `Environment`: on `START` message it schedules timer that sends `TICK` message using `tick_interval` (in seconds), increments its tick counter (single source of true time), notifies drones, and schedules the next tick.
- On every `TICK`, each drone sends an `UPDATE_POSITION` message to the environment with position and election state.
- `Environment` handles drone-to-drone communication through `SEND_LOCAL` and `DELIVER` wrapper messages. When drone wants to send message to another drone, it puts it to SEND_LOCAL message as payload and sends wrapped message to environment. When environment retransmits message to receiver, it puts original payload to DELIVER message.
- Drones process and answer to messages immediately after receiving. It means that drone can send several messages during a TICK. That might become a problem on large swarm scales so we may add to drone some kind of outcoming stack later.
- `Drawer` renders drone positions and a right-side timing/debug panel using `pygame`.
- The environment can randomly kill one leader (low probability per tick) to trigger re-election and resilience behavior.

### Leader election logic

- Leader election is handled entirely by `Drone`.
- Both election and heartbeat propagation use `LEADER` messages.
- Each drone stores `leader_id`, `leader_version`, `leader_tick`, `heartbeat_interval`, and `timeout`.
- When drone receives `LEADER` message, it first compares versions - newer version means more recent information, new leader is accepted, message is propagated to neighbors.
- If versions are the same, it compares `leader_id` - higher id is preferable.
- If both `leader_version` and `leader_id` are the same, it means that drone received a heartbeat from its current leader. If received tick is more recent, drone's leader_tick is updated and message is propagated to neighbors.
- If `leader_version`, `leader_id` and `leader_tick` from received `LEADER` message are all the same as ones held by drone or worse, it discards the message.
- If a leader becomes silent for too long (`current_tick - leader_tick > timeout`), a drone starts a new election by incrementing version, promoting itself, and broadcasting `LEADER`.
- When a leader fails or swarms reconnect, several swarms merge or group of drones gets separated from a swarm, the best available leader naturally gets accepted by all drones in a swarm.

**Heartbeat specifics:** 

- Swarm leader periodically (2 ticks by default) sends messages indicating that he is alive, called heartbeat.
- On each `TICK`, each drone checks how much time has passed since the last heartbeat and compares it to its timeout (randomized between 6 and 9 ticks).
- Drone who detects that leader heartbeat was not received for a long time, becomes new leader candidate and  starts new leader election: increments version, sets leader_id to its own id, refreshes leader_tick and sends LEADER message to other drones.
- Heartbeat tick must be refreshed only by current leader or leader candidate, this prevents infinite heartbeat retransmission: old heartbeat is discarded by drones who have already received it.

## Installation

### Prerequisites

1. Install Python (recommended `3.11+`):  
[https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Install Git:  
[https://git-scm.com/downloads](https://git-scm.com/downloads)
3. Verify installation:
```bash
python --version
git --version
  ```

### Clone repository

```bash
git clone https://github.com/PavMash/DNP-Drone-Swarm.git
cd DNP-Drone-Swarm
```

### Create and activate virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Run the program

```bash
python main.py
```

### Stopping the simulation:
- Close the `pygame` window, or
- Press `Ctrl + C` in the terminal.