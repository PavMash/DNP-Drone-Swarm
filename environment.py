import pykka
import threading
from message_type import MessageType

class Environment(pykka.ThreadingActor):

    def __init__(self, radius, tick_interval=0.05):
        super().__init__()
        self.radius = radius
        self.tick_interval = tick_interval

        self.current_tick = 0
        self.drones = {}  # actor_ref -> {position}

        self.running = False
        self.timer = None


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
            self.drones[message["drone"]] = {
                "position": message["position"]
            }

        elif msg_type == MessageType.UPDATE_POSITION:
            self.drones[message["drone"]]["position"] = message["position"]

        elif msg_type == MessageType.SEND_LOCAL:
            self.route_local(message["sender"], message["payload"])
    

    def on_failure(self, exception_type, exception_value, traceback):
        if self.timer:  
                self.timer.cancel()

        print(f"[ENV CRASH] {exception_value}")


    def schedule_next_tick(self):
        if not self.running:
            return

        self.timer = threading.Timer(self.tick_interval, self.send_tick)
        self.timer.start()


    def send_tick(self):
        self.actor_ref.tell({"type": MessageType.TICK})


    def handle_tick(self):
        self.current_tick += 1
        
        # 1. Notify all drones
        for drone_ref in self.drones:
            drone_ref.tell({
                "type": MessageType.TICK,
                "tick": self.current_tick
            })

        # 2. Schedule next tick
        self.schedule_next_tick()


    def route_local(self, sender_ref, payload):
        sender_pos = self.drones[sender_ref]["position"]

        for ref, data in self.drones.items():
            if ref == sender_ref:
                continue

            if self.in_range(sender_pos, data["position"]):
                ref.tell({
                    "type": MessageType.DELIVER,
                    "payload": payload
                })
    

    def in_range(self, p1, p2):
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        return dx*dx + dy*dy <= self.radius * self.radius