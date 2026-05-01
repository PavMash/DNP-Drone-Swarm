import pykka

from message_type import MessageType
import random
import math


class Drone(pykka.ThreadingActor):
    TARGET_RADIUS = 10  # Radius of the target area around the center

    def __init__(
        self,
        drone_id,
        position,
        env_ref,
        heartbeat_interval=2,
        base_timeout=6,
        timeout_jitter=3,
        field_center=(50, 50),
    ):
        super().__init__()

        # Identity
        self.id = drone_id
        self.env = env_ref

        # Position
        self.position = position

        # Field center
        self.field_center = field_center

        # Time
        self.current_tick = 0

        # Leader state
        self.leader_id = drone_id
        self.leader_version = 0
        self.leader_tick = 0

        # Timing config
        self.heartbeat_interval = heartbeat_interval
        self.timeout = base_timeout + random.randint(0, timeout_jitter)

        # Leader election stability
        self._last_leader_id = self.leader_id
        self._last_leader_version = self.leader_version
        self._leader_stable_ticks = 0
        self._leader_stable_required = (
            30  # Number of ticks leader must be stable before moving
        )

        # dead
        self.dead = False

    def on_receive(self, message):
        if self.dead:
            return
        msg_type = message.get("type")

        if msg_type == MessageType.TICK:
            self.on_tick(message["tick"])

        elif msg_type == MessageType.DELIVER:
            self.handle_message(message["payload"])

    def on_failure(self, exception_type, exception_value, traceback):
        print(f"[ENV CRASH] {exception_value}")

    # --- Tick handling logic ---
    def on_tick(self, tick):
        self.current_tick = tick
        # 1. Move
        # Only move if leader election is stable for N ticks
        if self.leader_election_stable():
            if hasattr(self, "move_target") and self.move_target is not None:
                self.move()
        # Track leader stability
        if (
            self.leader_id == self._last_leader_id
            and self.leader_version == self._last_leader_version
        ):
            self._leader_stable_ticks += 1
        else:
            self._leader_stable_ticks = 0
            self._last_leader_id = self.leader_id
            self._last_leader_version = self.leader_version

        # 2. Send position update
        self.update_position()
        # Leader always sends MOVE_COMMAND to all (center)
        if self.is_leader():
            center = self.field_center
            self.move_target = center

            self.env.tell(
                {
                    "type": MessageType.SEND_LOCAL,
                    "sender": self.actor_ref,
                    "payload": {"type": MessageType.MOVE_COMMAND, "target": center},
                }
            )

        # 3. Check leader timeout
        self.check_leader_timeout()

        # 4. Leader sends heartbeat
        if self.is_leader() and self.current_tick % self.heartbeat_interval == 0:
            self.leader_tick = self.current_tick
            self.send_leader_message()

    def leader_election_stable(self):
        # Returns True if leader_id and leader_version have not changed for N ticks.

        return self._leader_stable_ticks >= self._leader_stable_required

    def update_position(self):
        self.env.tell(
            {
                "type": MessageType.UPDATE_POSITION,
                "drone": self.actor_ref,
                "position": self.position,
                "is_leader": self.is_leader(),
                "leader_id": self.leader_id,
                "leader_version": self.leader_version,
                "leader_tick": self.leader_tick,
                "timeout": self.timeout,
                "leader_stable_ticks": self._leader_stable_ticks,
                "leader_stable_required": self._leader_stable_required,
                "dead": self.dead,
            }
        )

    # --- Message handling logic ---
    def handle_message(self, msg):
        msg_type = msg["type"]
        if msg_type == MessageType.LEADER:
            self.handle_leader_message(msg)

        elif msg_type == MessageType.MOVE_COMMAND:  # is the target payload used?
            # Only accept move command if not leader and election is finished
            if not self.is_leader() and self.leader_id is not None:
                self.move_target = msg.get("target", (0, 0))
        elif msg_type == MessageType.DEAD:
            self.dead = True
            # Immediately send update to environment about death
            self.update_position()

    # --- Movement logic (placeholder) ---
    def move(self):
        if not hasattr(self, "move_target") or self.move_target is None:
            return
        center_x, center_y = self.field_center

        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, self.TARGET_RADIUS)
        tx = center_x + r * math.cos(angle)
        ty = center_y + r * math.sin(angle)
        # self.move_target = (tx, ty)
        x, y = self.position
        # tx, ty = self.move_target
        dx = tx - x
        dy = ty - y
        dist = (dx**2 + dy**2) ** 0.5
        if dist < 0.1:
            # Already at target
            return
        # Move step (max step size = 1.0 per tick)
        step = min(1.0, dist)
        nx = x + dx / dist * step
        ny = y + dy / dist * step
        self.position = (nx, ny)

    # --- Leader election logic ---
    def is_leader(self):
        return self.leader_id == self.id

    def check_leader_timeout(self):
        if self.current_tick - self.leader_tick > self.timeout:
            # Become new leader
            self.leader_version += 1
            self.leader_id = self.id
            self.leader_tick = self.current_tick
            print(
                f"[LEADER ELECTION] Drone {self.id} starts new election:  new leader {self.leader_id} (version {self.leader_version})"
            )

            # Immediately announce
            self.send_leader_message()

    def handle_leader_message(self, msg):
        incoming = (msg["version"], msg["leader_id"], msg["tick"])

        current = (self.leader_version, self.leader_id, self.leader_tick)

        # Accept only strictly better info
        # - If version is higher -> accept new leader, propagate further
        # - If version is the same but leader_id is higher -> accept new leader, propagate further
        # - If version and leader_id are the same, but tick is more recent ->
        #   fresh heartbeat from leader, update state and propogate further
        # - Otherwise -> no update and propogation needed
        if incoming > current:
            self.leader_version = msg["version"]
            self.leader_id = msg["leader_id"]
            self.leader_tick = msg["tick"]
            self.send_leader_message()

    def make_leader_message(self):
        return {
            "type": MessageType.LEADER,
            "leader_id": self.leader_id,
            "version": self.leader_version,
            "tick": self.leader_tick,
        }

    def send_leader_message(self):
        self.env.tell(
            {
                "type": MessageType.SEND_LOCAL,
                "sender": self.actor_ref,
                "payload": self.make_leader_message(),
            }
        )
