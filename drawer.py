import pygame
import threading
import queue
from typing import List, Dict, Any
from global_state import GlobalSyncedContainer


class Drawer:
    def __init__(self, state_container: GlobalSyncedContainer, field_size=100, window_size=800):
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
        self.PURPLE = (148, 0, 211)
        self.CYAN = (0, 170, 170)
        self.YELLOW = (220, 200, 0)
        self.PINK = (255, 105, 180)
        self.BROWN = (139, 69, 19)
        self.GRAY = (200, 200, 200)
        self.colour_array = [
            self.RED,
            self.BLUE,
            self.GREEN,
            self.ORANGE,
            self.PURPLE,
            self.CYAN,
            self.YELLOW,
            self.PINK,
            self.BROWN,
        ]
        self.leader_color_map: dict[tuple[int, int], tuple[int, int, int]] = {}

    def start(self):
        """Start the drawer (pygame runs on main thread)."""
        self.running = True
        # Start background thread to fetch drone positions
        self.updater_thread = threading.Thread(target=self._update_positions, daemon=True)
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
            time.sleep(1/30.0)

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
                    screen,
                    self.BLACK,
                    (0, 0, self.window_size, self.window_size),
                    2
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

    def _get_leader_key(self, drone_data: Dict[str, Any]) -> tuple[int, int] | None:
        """Build a stable leader identifier from election version and leader id."""
        leader_id = drone_data.get("leader_id")
        leader_version = drone_data.get("leader_version")
        if leader_id is None or leader_version is None:
            return None
        return leader_version, leader_id

    def _get_color_for_leader(self, leader_key: tuple[int, int] | None) -> tuple[int, int, int]:
        """Assign and reuse one color for each unique leader election result."""
        if leader_key is None:
            return self.GRAY
        if leader_key not in self.leader_color_map:
            color_index = len(self.leader_color_map) % len(self.colour_array)
            self.leader_color_map[leader_key] = self.colour_array[color_index]
        return self.leader_color_map[leader_key]

    def _resolve_drone_style(self, drone_data: Dict[str, Any]) -> tuple[tuple[int, int, int], tuple[int, int, int], str]:
        """Choose the drone fill color, label color, and caption for rendering."""
        drone_id = drone_data.get("drone_id", 0)
        is_leader = drone_data.get("is_leader", False)
        leader_key = self._get_leader_key(drone_data)

        if is_leader:
            color = self._get_color_for_leader(leader_key)
            return color, color, f"{drone_id} Leader"

        if leader_key is not None and drone_data.get("leader_id") != drone_id:
            color = self._get_color_for_leader(leader_key)
            return color, self.BLACK, str(drone_id)

        return self.GRAY, self.BLACK, str(drone_id)

    def _draw_drone(self, screen: pygame.Surface, drone_data: Dict[str, Any]):
        """Draw a single drone on the screen."""
        position = drone_data.get("position", (0, 0))
        
        # Scale position from field coordinates to screen coordinates
        x = int((position[0] / self.field_size) * self.window_size)
        y = int((position[1] / self.field_size) * self.window_size)
        
        # Clamp to screen bounds
        x = max(0, min(x, self.window_size - 1))
        y = max(0, min(y, self.window_size - 1))

        color, font_color, caption = self._resolve_drone_style(drone_data)
        
        # Draw drone as a circle
        radius = 5
        pygame.draw.circle(screen, color, (x, y), radius)
        
        # Draw drone ID as text
        font = pygame.font.Font(None, 24)
        text = font.render(caption, True, font_color)
        screen.blit(text, (x + 8, y - 8))
