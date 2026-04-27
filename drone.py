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
        self.leader_tick = 0

        # Timing config
        self.heartbeat_interval = heartbeat_interval
        self.timeout = base_timeout + random.randint(0, timeout_jitter)

        # Swarm size flood state
        self.swarm_size_requests = set() # Protection for duplicated answers to requests
        self.active_swarm_req_id = None
        self.active_swarm_set = set()
        self.swarm_size_responses = set()  # (req_id, drone_id) Protection for duplicated answers to responses



    def on_receive(self, message):
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
        # print(f"[DRONE {self.id}] thinks leader is {self.leader_id}")
        # 1. Move
        # self.move()

        # 2. Send position update
        self.env.tell({
            "type": MessageType.UPDATE_POSITION,
            "drone": self.actor_ref,
            "position": self.position,
            "is_leader": self.is_leader(),
        })


        # Leader initiates new SWARM_SIZE_REQUEST only if the previous is done
        if self.is_leader() and self.current_tick % 60 == 0:
            if self.active_swarm_req_id is not None:
                return
            print(f"Leader {self.id} initiating SWARM_SIZE_REQUEST")
            req_id = f"{self.id}_{self.current_tick}"
            self.active_swarm_req_id = req_id
            self.active_swarm_set = set([self.id])
            self.env.tell({
                "type": MessageType.SEND_LOCAL,
                "sender": self.actor_ref,
                "payload": {
                    "type": MessageType.SWARM_SIZE_REQUEST,
                    "req_id": req_id,
                    "leader_ref": self.actor_ref
                }
            })
        # Reset active request after timeout
        if self.active_swarm_req_id is not None:
            req_tick = int(self.active_swarm_req_id.split('_')[1])
            if self.current_tick - req_tick >= 80:
                self.active_swarm_req_id = None
                self.active_swarm_set = set()
                self.swarm_size_responses = set()
                self.swarm_size_requests = set()

        # 3. Check leader timeout
        self.check_leader_timeout()

        # 4. Leader sends heartbeat
        if self.is_leader() and self.current_tick % self.heartbeat_interval == 0:
            self.leader_tick = self.current_tick
            self.send_leader_message()


    # --- Message handling logic ---
    def handle_message(self, msg):
        msg_type = msg["type"]
        if msg_type == MessageType.LEADER:
            self.handle_leader_message(msg)

        elif msg_type == MessageType.SWARM_SIZE_REQUEST:
            req_id = msg.get("req_id")
            if self.is_leader():
                return
            if req_id not in self.swarm_size_requests:
                self.swarm_size_requests.add(req_id)
                response = {
                    "type": MessageType.SWARM_SIZE_RESPONSE,
                    "drone_id": self.id,
                    "req_id": req_id
                }
                self.env.tell({
                    "type": MessageType.SEND_LOCAL,
                    "sender": self.actor_ref,
                    "payload": response
                })
                self.env.tell({
                    "type": MessageType.SEND_LOCAL,
                    "sender": self.actor_ref,
                    "payload": msg
                })

        elif msg_type == MessageType.SWARM_SIZE_RESPONSE:
            req_id = msg.get("req_id")
            drone_id = msg.get("drone_id")
            key = (req_id, drone_id)
            if key in self.swarm_size_responses:
                return
            self.swarm_size_responses.add(key)
            if self.is_leader():
                if self.active_swarm_req_id != req_id:
                    return
                self.active_swarm_set.add(drone_id)
                print(f"[LEADER {self.id}] Swarm size for req_id={req_id}: {len(self.active_swarm_set)}")
            else:
                self.env.tell({
                    "type": MessageType.SEND_LOCAL,
                    "sender": self.actor_ref,
                    "payload": msg
                })


    # --- Movement logic (placeholder) ---
    def move(self):
        dx = random.uniform(-1, 1)
        dy = random.uniform(-1, 1)

        self.position = (
            self.position[0] + dx,
            self.position[1] + dy
        )


    # --- Leader election logic ---
    def is_leader(self):
        return self.leader_id == self.id
    

    def check_leader_timeout(self):
        if self.current_tick - self.leader_tick > self.timeout:
            # Become new leader
            self.leader_version += 1
            self.leader_id = self.id
            self.leader_tick = self.current_tick
            print(f"[LEADER ELECTION] Drone {self.id} starts new election:  new leader {self.leader_id} (version {self.leader_version})")

            # Immediately announce
            self.send_leader_message()

    
    def handle_leader_message(self, msg):
        incoming = (
            msg["version"],
            msg["leader_id"],
            msg["tick"]
        )

        current = (
            self.leader_version,
            self.leader_id,
            self.leader_tick
        )

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
            "tick": self.leader_tick
        }


    def send_leader_message(self):
        self.env.tell({
            "type": MessageType.SEND_LOCAL,
            "sender": self.actor_ref,
            "payload": self.make_leader_message()
        })