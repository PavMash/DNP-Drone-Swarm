from pykka import ActorRef
from drone import Drone

from threading import Lock
from typing import Any


class GlobalSyncedContainer:
    drones: dict[ActorRef[Drone], dict[str, Any]]

    def __init__(self):
        self._lock = Lock()
        self.drones = {}
        self.current_tick = 0

    def register_drone(
        self, drone_ref: ActorRef[Drone], drone_id: int, position: tuple[float, float]
    ):
        with self._lock:
            self.drones[drone_ref] = {
                "drone_id": drone_id,
                "position": position,
                "leader_id": drone_id,
                "is_leader": True,
                "dead": False,
                "tx_until_tick": 0,
                "rx_until_tick": 0,
            }

    def update_position(
        self, drone_ref: ActorRef[Drone], position: tuple[float, float], is_leader: bool
    ):
        with self._lock:
            if drone_ref in self.drones:
                self.drones[drone_ref]["position"] = position
                self.drones[drone_ref]["is_leader"] = is_leader

    def set_current_tick(self, tick: int):
        with self._lock:
            self.current_tick = tick

    def mark_signal_sent(self, drone_ref: ActorRef[Drone], pulse_ticks: int = 10):
        with self._lock:
            if drone_ref in self.drones:
                self.drones[drone_ref]["tx_until_tick"] = (
                    self.current_tick + pulse_ticks
                )

    def mark_signal_received(self, drone_ref: ActorRef[Drone], pulse_ticks: int = 10):
        with self._lock:
            if drone_ref in self.drones:
                self.drones[drone_ref]["rx_until_tick"] = (
                    self.current_tick + pulse_ticks
                )

    def get_items_snapshot(self) -> list[tuple[ActorRef[Drone], dict[str, Any]]]:
        with self._lock:
            return [
                (
                    ref,
                    {
                        "drone_id": data["drone_id"],
                        "position": data["position"],
                        "dead": data["dead"],
                        "is_leader": data["is_leader"],
                        "tx_until_tick": data["tx_until_tick"],
                        "rx_until_tick": data["rx_until_tick"],
                    },
                )
                for ref, data in self.drones.items()
            ]

    def get_positions_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "drone_id": data["drone_id"],
                    "position": data["position"],
                    "is_leader": data["is_leader"],
                    "leader_id": data["leader_id"],
                    "dead": data["dead"],
                    "is_sending": data["tx_until_tick"] >= self.current_tick,
                    "is_receiving": data["rx_until_tick"] >= self.current_tick,
                }
                for data in self.drones.values()
            ]

    def get_position(self, drone_ref: ActorRef[Drone]) -> tuple[float, float] | None:
        with self._lock:
            if drone_ref not in self.drones:
                return None
            return self.drones[drone_ref]["position"]

    def mark_drone_leader(self, drone_ref: ActorRef[Drone], leader_id: int) -> None:
        with self._lock:
            self.drones[drone_ref]["leader_id"] = leader_id

    def mark_dead_drone(self, drone_ref: ActorRef[Drone]) -> None:
        with self._lock:
            self.drones[drone_ref]["dead"] = True


container = GlobalSyncedContainer()
