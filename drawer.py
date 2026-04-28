import pygame
import threading
import queue
from typing import List, Dict, Any
from global_state import GlobalSyncedContainer


class Drawer:
    def __init__(self, state_container: GlobalSyncedContainer, field_size=100, window_size=800, panel_width=360):
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
        self.panel_width = panel_width
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
        self.PANEL_BG = (245, 245, 245)
        self.PANEL_BORDER = (170, 170, 170)
        self._panel_scroll = 0
        self._panel_scroll_step = 3

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
        screen = pygame.display.set_mode((self.window_size + self.panel_width, self.window_size))
        pygame.display.set_caption("Drone Swarm Simulation")
        clock = pygame.time.Clock()

        try:
            while self.running:
                # Handle pygame events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        break
                    if event.type == pygame.MOUSEWHEEL:
                        mx, _ = pygame.mouse.get_pos()
                        if mx >= self.window_size:
                            self._panel_scroll = max(0, self._panel_scroll - event.y * self._panel_scroll_step)

                # Clear screen
                screen.fill(self.WHITE)

                # Draw field boundary
                pygame.draw.rect(
                    screen,
                    self.BLACK,
                    (0, 0, self.window_size, self.window_size),
                    2
                )
                self._draw_side_panel(screen)
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

    def _draw_side_panel(self, screen: pygame.Surface):
        """Draw a debug panel with timing data for each drone."""
        # Draw right-side panel background and its left border separator.
        panel_x = self.window_size
        panel_rect = (panel_x, 0, self.panel_width, self.window_size)
        pygame.draw.rect(screen, self.PANEL_BG, panel_rect)
        pygame.draw.line(screen, self.PANEL_BORDER, (panel_x, 0), (panel_x, self.window_size), 2)

        # Prepare sorted input data and fonts used by the panel.
        drones = sorted(self._get_drones(), key=lambda d: d.get("drone_id", 0))
        font = pygame.font.Font(None, 20)
        font_small = pygame.font.Font(None, 18)

        x = panel_x + 10
        y = 10
        line_h = 18
        scrollbar_w = 8
        scrollbar_gap = 6

        # Render centered panel title and current global tick.
        header = "Timing data"
        header_surface = font.render(header, True, self.BLACK)
        header_x = panel_x + (self.panel_width - header_surface.get_width()) // 2
        screen.blit(header_surface, (header_x, y))
        y += line_h + 6

        if drones:
            current_tick = drones[0].get("current_tick", 0)
        else:
            current_tick = 0
        screen.blit(font_small.render(f"tick={current_tick}", True, self.BLACK), (x, y))
        y += line_h + 8

        # Convert raw drone dicts into normalized table rows.
        rows: list[dict[str, str]] = []
        for drone_data in drones:
            drone_id = drone_data.get("drone_id", 0)
            leader_id = drone_data.get("leader_id")
            leader_tick = drone_data.get("leader_tick", 0)
            timeout = drone_data.get("timeout", 0)
            stable_ticks = drone_data.get("leader_stable_ticks", 0)
            stable_required = drone_data.get("leader_stable_required", 0)
            position = drone_data.get("position", (0.0, 0.0))

            since_hb = max(0, current_tick - int(leader_tick or 0))
            timeout_left = int(timeout or 0) - since_hb if timeout else 0

            rows.append(
                {
                    "id": str(drone_id),
                    "leader": "-" if leader_id is None else str(int(leader_id)),
                    "since": str(since_hb),
                    "left": str(timeout_left),
                    "stable": f"{stable_ticks}/{stable_required}" if stable_required else "-",
                    "coord_x": f"{float(position[0]):.3f}",
                    "coord_y": f"{float(position[1]):.3f}",
                }
            )

        # Column identifiers and user-facing headers.
        columns = [
            ("id", "id"),
            ("leader", "Leader id (V)"),
            ("since", "ticks since HB"),
            ("left", "ticks before timeout"),
            ("stable", "stable ticks"),
            ("coord_x", "coord X"),
            ("coord_y", "coord Y"),
        ]

        def text_w(s: str) -> int:
            return font_small.size(s)[0]

        # Measure minimal column width from headers and all row values.
        col_w: dict[str, int] = {}
        for key, label in columns:
            col_w[key] = max(text_w(part) for part in label.split())
        for r in rows:
            for key, _ in columns:
                col_w[key] = max(col_w[key], text_w(r.get(key, "")))

        # Fit table into panel width and reserve space for the scrollbar.
        padding = 8
        available_w = self.panel_width - 20 - scrollbar_w - scrollbar_gap  # left/right margin and scrollbar
        total_w = sum(col_w[k] for k, _ in columns) + padding * (len(columns) - 1)
        if total_w > available_w:
            padding = 4

        # Compute x-position for each column start.
        col_x: dict[str, int] = {}
        cur_x = x
        for idx, (key, _) in enumerate(columns):
            col_x[key] = cur_x
            cur_x += col_w[key]
            if idx < len(columns) - 1:
                cur_x += padding

        # Draw multi-line column headers (one word per line), centered per column.
        max_header_lines = max(len(label.split()) for _, label in columns)
        header_y = y
        for key, label in columns:
            words = label.split()
            for idx, word in enumerate(words):
                word_surface = font_small.render(word, True, self.BLACK)
                word_x = col_x[key] + (col_w[key] - word_surface.get_width()) // 2
                word_y = header_y + idx * line_h
                screen.blit(word_surface, (word_x, word_y))

        # Compute visible slice based on scroll position and available height.
        sep_top = header_y - 4
        data_start_y = header_y + max_header_lines * line_h + 6

        max_lines = max(0, (self.window_size - data_start_y - 10) // line_h)
        max_scroll = max(0, len(drones) - max_lines)
        if self._panel_scroll > max_scroll:
            self._panel_scroll = max_scroll

        start = self._panel_scroll
        end = start + max_lines
        visible_drones = drones[start:end]
        visible_rows = rows[start:end]

        # Draw vertical separators between columns.
        sep_bottom = data_start_y + max_lines * line_h + 2
        for key, _ in columns[:-1]:
            sep_x = col_x[key] + col_w[key] + (padding // 2)
            pygame.draw.line(screen, self.PANEL_BORDER, (sep_x, sep_top), (sep_x, sep_bottom), 1)

        # Render visible row values with column-centered alignment.
        y = data_start_y
        for drone_data, row in zip(visible_drones, visible_rows):
            color = self.BLACK
            if drone_data.get("is_leader", False):
                color = self._get_color_for_leader(self._get_leader_key(drone_data))
            else:
                timeout = drone_data.get("timeout", 0)
                leader_tick = drone_data.get("leader_tick", 0)
                since_hb = max(0, current_tick - int(leader_tick or 0))
                timeout_left = int(timeout or 0) - since_hb if timeout else 0
                if timeout_left <= 1 and timeout:
                    color = self.RED

            for key, _ in columns:
                value_surface = font_small.render(row[key], True, color)
                value_x = col_x[key] + (col_w[key] - value_surface.get_width()) // 2
                screen.blit(value_surface, (value_x, y))
            y += line_h

        # Draw mini scrollbar (track + thumb) on the panel's right edge.
        track_x = panel_x + self.panel_width - scrollbar_w - 2
        track_y = data_start_y
        track_h = max(20, self.window_size - track_y - 8)
        pygame.draw.rect(screen, (220, 220, 220), (track_x, track_y, scrollbar_w, track_h))
        pygame.draw.rect(screen, self.PANEL_BORDER, (track_x, track_y, scrollbar_w, track_h), 1)

        if len(drones) > 0 and max_lines > 0:
            visible_ratio = min(1.0, max_lines / len(drones))
            thumb_h = max(14, int(track_h * visible_ratio))
            scroll_ratio = (self._panel_scroll / max_scroll) if max_scroll > 0 else 0.0
            thumb_y = track_y + int((track_h - thumb_h) * scroll_ratio)
            pygame.draw.rect(screen, (130, 130, 130), (track_x + 1, thumb_y, scrollbar_w - 2, thumb_h))

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
