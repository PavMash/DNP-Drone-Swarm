# DNP Drone Swarm

## Model

- There is 2D field with cordinates (square or possibly rectangle)
- There is arbitrary number of drones spawned within this field (about 1-100 drones, possibly more)
- Every drone has same fixed radius of communication. Within that radius drone can send messages to other drones
- Purpose of swarm leader is to lead drones to center of field and form a figure of drones (figure is chosen based on swarm size)
- If there are no other drones witin communication radius of a drone, it considers itself as a swarm leader (swarm of single drone)
- Messages from leader and other drones propogate from neighbors to neighbors eventually covering whole swarm (Gossip algorithm)
-  Лидер роя периодически посылает сигналы о том, что он жив. Лидер может умереть или дроны в рое могут счесть его мертвым, если давно не получали от него сигнал. Тогда запускается процесс нового лидера

## Global tasks

- [x] Write drone agent and its logic of message processing and message exchange with neighbors
- [ ] Write environment for drones (field, pull of drones, initialization)
    Rest of subtasks:
    - [ ] Handle drones trying to go out of field boundaries
- [x] Implement Gossip algorithm for global message excahnge in swarm
- [x] Implement leader election algorithm
- [ ] Implement figure forming algorithm
    - [ ] Implement swarm size resolution 
    - [ ] Implement moving and figure forming messages and processing of these messages
    - [ ] Implement figure type resolution based on swarm size
- [ ] Visualization through PyGame or HTML
- [ ] Report

## Design decisions and architecture description

### Environment, drones and simulation design 

- All drones and environment run in a single process as separate threads. This is relatively simple and fits simulation requirements.
- We use Pikka library for drone and environment simulation. Read about Pikka and actor model in ![oficial documentation](https://pykka.readthedocs.io/stable/)
    ```
    pip install pykka
    ```
- Both drones and environment are Pikka actors. When drone wants to communicate to other drones, it send message to environment that checks drone neighborhood and delivers message those who can receive it
- Drones, Environemt and main function (that initializes drones and environment and starts simulation) communicate using messages of types listed in message_type.py (message documentation is here as well)
- Time simulation is handled by Environment. On START message received it schedules timer that sends TICK message to Environment after specifed tick_interval (in seconds). When TICK message is received by Environment, it increments its tick counter (single source of true time), sends TICK message to all drones and reschedules timer
- On every TICK drone sends UPDATE_POSITION message to Environment
- Environemt handles drone-to-drone communication with SEND_LOCAL and DELIVER wrapper messages. When drone wants to send message to another drone, it puts it to SEND_LOCAL message as payload and sends wrapped message to environment. When environment retransmitts message to receiver, it puts original payload to DELIVER message

### Leader election logic

- Leader election is handled entirely by Drone
- Both leader election and heartbit are handled with LEADER messages
- Each drone holds leader_id, leader_version, leader_tick, heartbeat_interval and timeout
- When drone receives LEADER message, it first compares versions - newer version means more recent information, new leader is accepted, message is propogated to neigthbors. 
- If versions are the same, it compares leader_id - higher id is preferable. If new leader is accepted, message is propogated to neighbors.
- If both version and leader_id are the same, it means that drone received a heartbeat from its current leader. If received tick is more recent, drone's leader_tick is updated and message is propogated to neighbors
- If version, leader_id and tick from received LEADER message are all the same as ones held by drone or worse, it discards message
- When swarm leader dies, several swarms merge or group of drones gets separated from a swarm, best available leader naturally gets accepted by all drones in a swarm

**Heartbeat specifics:** 
- Swarm leader periodically (2 ticks by default) sends messages indicating that he is alive, we call them heartbeat
- On each TICK drones within a swarm check how much time has passed since the last received heartbeat (leader_tick) and compare it with timeout (randomized between 6 and 9 ticks)
- Drone who detects that leader heartbeat was not received for a long time, becomes new leader candidate and  starts new leader election: increments version, sets leader_id to its own id, refreshes leader_tick and sends LEADER message to other drones
- Heartbit tick must be refreshed only by current leader or leader candidate, this prevents infinite heartbeat retransmission: old heartbeat is discarded by drones who has alredy received it

## General commit format

Коммиты пишем на английском, чтобы потом репорт легче составлять

```
<what you've done in general>:

- <feature 1>
- <feature 2>
- ...
```

**Example:**

```
Add README.md:

- Write specification of model
- Write list of main tasks
- Write commit format section
```