import pykka
from message_type import MessageType
import random

class Drone(pykka.ThreadingActor):
    def __init__(self, drone_id, position, env_ref,
                 heartbeat_interval=2,
                 base_timeout=6,
                 timeout_jitter=3):
        super().__init__()

        # Identity
        self.id = drone_id
        self.env = env_ref

        # Position
        self.position = position

        # Time
        self.current_tick = 0

        # Leader state
        self.leader_id = drone_id
        self.leader_version = 0
        self.leader_timestamp = 0  # in ticks

        # Timing config
        self.heartbeat_interval = heartbeat_interval
        self.timeout = base_timeout + random.randint(0, timeout_jitter)


    def on_receive(self, message):
        msg_type = message.get("type")

        if msg_type == MessageType.TICK:
            self.on_tick(message["tick"])

        elif msg_type == MessageType.DELIVER:
            self.handle_message(message["payload"])

    
    def on_failure(self, exception_type, exception_value, traceback):
        print(f"[ENV CRASH] {exception_value}")

    def on_tick(self, tick):
        self.current_tick = tick

        # 1. Move
        self.move()

        # 2. Send position update
        self.env.tell({
            "type": MessageType.UPDATE_POSITION,
            "drone": self.actor_ref,
            "position": self.position
        })

        # 3. Check leader timeout
        self.check_leader_timeout()

        # 4. Leader sends heartbeat
        if self.is_leader() and self.current_tick % self.heartbeat_interval == 0:
            self.leader_timestamp = self.current_tick
            self.send_leader_message()


    # Movement (placeholder)
    def move(self):
        dx = random.uniform(-1, 1)
        dy = random.uniform(-1, 1)

        self.position = (
            self.position[0] + dx,
            self.position[1] + dy
        )


    def is_leader(self):
        return self.leader_id == self.id
    

    def check_leader_timeout(self):
        if self.current_tick - self.leader_timestamp > self.timeout:
            # Become new leader
            self.leader_version += 1
            self.leader_id = self.id
            self.leader_timestamp = self.current_tick

            # Immediately announce
            self.send_leader_message()

    
    def handle_message(self, msg):
        if msg["type"] == MessageType.LEADER:
            self.handle_leader_message(msg)

    
    def handle_leader_message(self, msg):
        incoming = (
            msg["version"],
            msg["leader_id"],
            msg["timestamp"]
        )

        current = (
            self.leader_version,
            self.leader_id,
            self.leader_timestamp
        )

        # Accept only strictly better info
        if incoming > current:
            self.leader_version = msg["version"]
            self.leader_id = msg["leader_id"]
            self.leader_timestamp = msg["timestamp"]

            # Forward new info
            self.send_leader_message()
    

    def make_leader_message(self):
        return {
            "type": MessageType.LEADER,
            "leader_id": self.leader_id,
            "version": self.leader_version,
            "timestamp": self.leader_timestamp
        }


    def send_leader_message(self):
        self.env.tell({
            "type": MessageType.SEND_LOCAL,
            "sender": self.actor_ref,
            "payload": self.make_leader_message()
        })