import pygame
import threading
import queue
from typing import List, Dict, Any
from global_state import GlobalSyncedContainer


class Drawer:
    def __init__(
        self, state_container: GlobalSyncedContainer, field_size=100, window_size=800
    ):
        """
        Initialize the drawer for visualizing drone positions.

        Args:
            state_container: Shared synchronized state container
            field_size: Size of the simulation field (assumed square)
            window_size: Size of the pygame window in pixels
        """
        self.state_container = state_container
        self.field_size = field_size
        self.window_size = window_size
        self.running = False
        self.updater_thread = None

        # Thread-safe queue for drone positions
        self.positions_queue = queue.Queue(maxsize=1)

        # Cache last known positions (fallback when queue is empty)
        self.last_drones = []

        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.BLUE = (0, 0, 255)
        self.RED = (255, 0, 0)
        self.GREEN = (0, 180, 0)
        self.ORANGE = (255, 140, 0)
        self.GRAY = (200, 200, 200)

    def start(self):
        """Start the drawer (pygame runs on main thread)."""
        self.running = True
        # Start background thread to fetch drone positions
        self.updater_thread = threading.Thread(
            target=self._update_positions, daemon=True
        )
        self.updater_thread.start()

    def stop(self):
        """Stop the drawer."""
        self.running = False
        if self.updater_thread:
            self.updater_thread.join(timeout=2)

    def _update_positions(self):
        """Background thread that fetches drone positions from environment."""
        import time

        while self.running:
            try:
                drones = self._get_drones()
                # Try to put latest positions (non-blocking, discard old data)
                try:
                    self.positions_queue.put_nowait(drones)
                except queue.Full:
                    # Queue is full, discard old data
                    try:
                        self.positions_queue.get_nowait()
                        self.positions_queue.put_nowait(drones)
                    except queue.Empty:
                        pass
            except Exception:
                pass

            # Update at 30 FPS
            time.sleep(1 / 30.0)

    def run(self):
        """Main pygame loop (runs on main thread)."""
        pygame.init()
        screen = pygame.display.set_mode((self.window_size, self.window_size))
        pygame.display.set_caption("Drone Swarm Simulation")
        clock = pygame.time.Clock()

        try:
            while self.running:
                # Handle pygame events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        break

                # Clear screen
                screen.fill(self.WHITE)

                # Draw field boundary
                pygame.draw.rect(
                    screen, self.BLACK, (0, 0, self.window_size, self.window_size), 2
                )
                try:
                    drones = self.positions_queue.get_nowait()
                    self.last_drones = drones  # Update cache
                except queue.Empty:
                    drones = self.last_drones  # Use cached positionspty:
                    # drones = []

                # Draw drones
                for drone_data in drones:
                    self._draw_drone(screen, drone_data)

                pygame.display.flip()
                clock.tick(30)  # 30 FPS

        finally:
            pygame.quit()

    def _get_drones(self) -> List[Dict[str, Any]]:
        """Get current drone positions from shared container."""
        drones = self.state_container.get_positions_snapshot()
        return drones if drones else []

    def _draw_drone(self, screen: pygame.Surface, drone_data: Dict[str, Any]):
        """Draw a single drone on the screen."""
        position = drone_data.get("position", (0, 0))
        drone_id = drone_data.get("drone_id", 0)
        is_leader = drone_data.get("is_leader", False)
        # is_sending = drone_data.get("is_sending", False)
        is_receiving = drone_data.get("is_receiving", False)
        dead = drone_data.get("dead", False)

        # Scale position from field coordinates to screen coordinates
        x = int((position[0] / self.field_size) * self.window_size)
        y = int((position[1] / self.field_size) * self.window_size)

        # Clamp to screen bounds
        x = max(0, min(x, self.window_size - 1))
        y = max(0, min(y, self.window_size - 1))

        color = self.BLUE
        # if is_leader:
        #     color = self.RED
        if is_receiving:
            color = self.GREEN
        if dead:
            color = self.BLACK
        # if is_sending:
        #     color = self.ORANGE

        # Draw drone as a circle
        radius = 5
        pygame.draw.circle(screen, color, (x, y), radius)

        # Draw drone ID as text
        font = pygame.font.Font(None, 24)
        text = font.render(str(drone_id), True, self.RED if is_leader else self.BLACK)
        screen.blit(text, (x + 8, y - 8))
