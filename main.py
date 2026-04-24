import random
from environment import Environment
from drone import Drone
from message_type import MessageType
from drawer import Drawer
from global_state import container

def main():
    # Simulation parameters
    NUM_DRONES = 30
    FIELD_SIZE = 100
    COMM_RADIUS = 15
    TICK_INTERVAL = 0.05  # seconds (real-time pacing)

    # 1. Start environment
    env = Environment.start(radius=COMM_RADIUS)

    # 2. Create and register drones
    for i in range(NUM_DRONES):
        position = (
            random.uniform(0, FIELD_SIZE),
            random.uniform(0, FIELD_SIZE)
        )

        drone = Drone.start(
            drone_id=i,
            position=position,
            env_ref=env
        )

        env.tell({
            "type": MessageType.REGISTER,
            "drone": drone,
            "drone_id": i,
            "position": position
        })

    # 3. Start drawer visualization
    drawer = Drawer(container, field_size=FIELD_SIZE, window_size=800)
    drawer.start()
    print("Drawer started...")

    # 4. Start simulation
    print("Starting simulation...")
    env.tell({"type": MessageType.START})

    # 5. Run pygame on main thread (blocking)
    try:
        drawer.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        drawer.stop()
        env.tell({"type": MessageType.STOP})

if __name__ == "__main__":
    main()