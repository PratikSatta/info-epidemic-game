"""
Base class for scrollable panels with fixed-size content areas.

Provides common scrolling functionality for panels that may have
more content than visible space.
"""

import pygame


class ScrollablePanel:
    """Base class for panels with scrollable content."""

    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.scroll_offset = 0
        self.max_scroll = 0
        self.content_height = 0
        self.header_height = 44  # Standard header height

    def get_content_rect(self) -> pygame.Rect:
        """Get the clipping rectangle for scrollable content."""
        return pygame.Rect(
            self.rect.x,
            self.rect.y + self.header_height,
            self.rect.width,
            self.rect.height - self.header_height
        )

    def update_scroll_bounds(self, total_content_height: int) -> None:
        """Calculate maximum scroll based on content height."""
        content_rect = self.get_content_rect()
        self.content_height = total_content_height
        self.max_scroll = max(0, total_content_height - content_rect.height)
        # Clamp current offset if content shrunk
        self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll))

    def handle_scroll(self, mouse_pos: tuple[int, int], scroll_y: int) -> bool:
        """Handle mouse wheel scrolling. Returns True if handled."""
        if self.rect.collidepoint(mouse_pos) and self.max_scroll > 0:
            self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset - scroll_y * 20))
            return True
        return False

    def adjust_point_for_scroll(self, point: tuple[int, int]) -> tuple[int, int]:
        """Adjust a click point to account for scroll offset."""
        return (point[0], point[1] + self.scroll_offset)

    def is_visible_in_scroll(self, item_rect: pygame.Rect) -> bool:
        """Check if an item rect is visible in the scrollable area."""
        content_rect = self.get_content_rect()
        scrolled_rect = item_rect.copy()
        scrolled_rect.y -= self.scroll_offset
        return scrolled_rect.bottom > content_rect.top and scrolled_rect.top < content_rect.bottom
