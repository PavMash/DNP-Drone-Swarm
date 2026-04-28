import pykka
import threading
import random

from global_state import container
from message_type import MessageType


class Environment(pykka.ThreadingActor):
    def __init__(
            self, radius, tick_interval=0.05, field_size=100, field_center=(50, 50)
    ):
        super().__init__()
        self.radius = radius
        self.tick_interval = tick_interval
        self.field_size = field_size
        self.field_center = field_center

        self.current_tick = 0

        self.running = False
        self.timer = None
        self.last_print_tick = 0  # Track when we last printed positions

    def on_receive(self, message):
        msg_type = message.get("type")

        if msg_type == MessageType.START:
            self.running = True
            self.schedule_next_tick()

        elif msg_type == MessageType.STOP:
            self.running = False
            if self.timer:
                self.timer.cancel()

        elif msg_type == MessageType.TICK:
            self.handle_tick()

        elif msg_type == MessageType.REGISTER:
            container.register_drone(
                drone_ref=message["drone"],
                drone_id=message["drone_id"],
                position=message["position"],
            )

        elif msg_type == MessageType.UPDATE_POSITION:
            container.update_position(
                message["drone"],
                message["position"],
                message.get("is_leader", False),
                message.get("leader_id"),
                message.get("leader_version", 0),
                message.get("leader_tick", 0),
                message.get("timeout", 0),
                message.get("leader_stable_ticks", 0),
                message.get("leader_stable_required", 0),
                message.get("dead", False),
            )
            container.check_end(self.field_center, 10.0)

        elif msg_type == MessageType.SEND_LOCAL:
            if message["payload"]["type"] == MessageType.LEADER:
                container.inc_leader_mgs_count()
            self.route_local(message["sender"], message["payload"])

    def on_failure(self, exception_type, exception_value, traceback):
        if self.timer:
            self.timer.cancel()

        print(f"[ENV CRASH] {exception_value}")

    # --- Time simulation logic ---
    def schedule_next_tick(self):
        if not self.running:
            return

        self.timer = threading.Timer(self.tick_interval, self.send_tick)
        self.timer.start()

    def send_tick(self):
        self.actor_ref.tell({"type": MessageType.TICK})

    def handle_tick(self):
        self.current_tick += 1
        container.set_current_tick(self.current_tick)
        drone_items = container.get_items_snapshot()

        if random.uniform(0, 1) >= 0.98:
            self.kill_first_leader()

        # 1. Notify all drones
        for drone_ref, _ in drone_items:
            drone_ref.tell({"type": MessageType.TICK, "tick": self.current_tick})

        # 2. Print drone positions every 1 second (20 ticks at 0.05s interval)
        if self.current_tick - self.last_print_tick >= 20:
            self.last_print_tick = self.current_tick
            self.print_positions()

        # 3. Schedule next tick
        self.schedule_next_tick()

    @staticmethod
    def kill_first_leader():
        for drone_ref, data in container.get_items_snapshot():
            if data["is_leader"] and not data["dead"]:
                drone_ref.tell(
                    {
                        "type": MessageType.DELIVER,
                        "payload": {
                            "type": MessageType.DEAD,
                        },
                    }
                )
                break

    # --- Message routing logic ---
    def route_local(self, sender_ref, payload):
        sender_pos = container.get_position(sender_ref)
        if sender_pos is None:
            return

        container.mark_signal_sent(sender_ref)

        drone_items = container.get_items_snapshot()

        for ref, data in drone_items:
            if ref == sender_ref:
                continue

            if self.in_range(sender_pos, data["position"]):
                container.mark_signal_received(ref)
                ref.tell({"type": MessageType.DELIVER, "payload": payload})

    # --- Monitoring logic ---
    def print_positions(self):
        positions = container.get_positions_snapshot()
        positions_str = "\n".join(
            [f"Drone {data['drone_id']}: {data['position']}" for data in positions]
        )
        print(f"[t={self.current_tick * self.tick_interval:.2f}s]\n{positions_str}")

    def in_range(self, p1, p2):
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        return dx * dx + dy * dy <= self.radius * self.radius
