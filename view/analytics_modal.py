"""
Real-Time Epidemic Analytics Modal for TU BCA Academic Project

Displays live S-E-I-R curves, R_t (effective reproduction number) tracking,
and epidemic phase annotations in an interactive overlay window.

Mathematical Foundation:
- SEIR compartmental model with waning immunity (SIRS variant)
- Effective reproduction number estimated from the incidence curve via the
  renewal equation, R_t = inc(t) / Σ w(s)·inc(t−s), where w is the active
  spread model's own generation-time distribution (Cori et al. 2013). It is
  measured rather than derived from β/γ because this model has no constant
  removal rate — see algorithm/reproduction_number.py.
- Epidemic threshold: R_t = 1.0 (below = decay, above = growth)

Academic Context:
This modal provides publication-quality visualizations and real-time
mathematical epidemiology metrics required for TU BCA 8th semester
final project defense presentations.
"""

import pygame
from view import theme


class AnalyticsModal:
    """
    Interactive epidemic analytics overlay displaying:
    - S(t), E(t), I(t), R(t) time-series trajectories
    - R_t effective reproduction number with epidemic threshold line
    - Phase annotations (Pre-countermeasure, Active Response, Crackdown)
    """

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, header_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.header_font = header_font
        self.visible = False

        # Graph rendering zones
        pad = 24
        header_h = 50
        graph_h = (self.rect.height - header_h - pad * 4) // 2

        self.seir_graph_rect = pygame.Rect(
            self.rect.x + pad,
            self.rect.y + header_h + pad,
            self.rect.width - pad * 2,
            graph_h
        )

        self.rt_graph_rect = pygame.Rect(
            self.rect.x + pad,
            self.seir_graph_rect.bottom + pad,
            self.rect.width - pad * 2,
            graph_h
        )

        self.close_button_rect = pygame.Rect(
            self.rect.right - 48,
            self.rect.y + 12,
            36,
            36
        )

    def toggle(self) -> None:
        self.visible = not self.visible

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Returns True if click was handled (close button)."""
        if not self.visible:
            return False
        if self.close_button_rect.collidepoint(pos):
            self.visible = False
            return True
        return self.rect.collidepoint(pos)  # Consume clicks inside modal

    def draw(self, surface: pygame.Surface, telemetry_history: list[dict]) -> None:
        if not self.visible:
            return
        if not telemetry_history:
            # Visible but with nothing to plot (a fresh game, or a game that was
            # just reset). Drop the flag rather than leaving an invisible
            # overlay that still swallows clicks -- handle_click gates on
            # self.visible, so the two must agree on whether the modal is
            # actually on screen.
            self.visible = False
            return

        # Semi-transparent backdrop overlay
        overlay = pygame.Surface((theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        # Main modal panel
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=16)
        pygame.draw.rect(surface, theme.ACCENT, self.rect, width=2, border_radius=16)

        # Header
        title = self.header_font.render("📊 REAL-TIME EPIDEMIC ANALYTICS", True, theme.ACCENT_BRIGHT)
        surface.blit(title, (self.rect.x + 24, self.rect.y + 16))

        # Close button
        mouse_pos = pygame.mouse.get_pos()
        close_hover = self.close_button_rect.collidepoint(mouse_pos)
        close_bg = theme.COLOR_DANGER if close_hover else theme.PANEL_BG_LIGHT
        pygame.draw.rect(surface, close_bg, self.close_button_rect, border_radius=6)
        pygame.draw.rect(surface, theme.PANEL_BORDER_BRIGHT, self.close_button_rect, width=1, border_radius=6)
        close_x = self.font.render("✕", True, theme.TEXT_HIGHLIGHT)
        surface.blit(close_x, (
            self.close_button_rect.centerx - close_x.get_width() // 2,
            self.close_button_rect.centery - close_x.get_height() // 2
        ))

        # Draw graphs
        self._draw_seir_graph(surface, telemetry_history)
        self._draw_rt_graph(surface, telemetry_history)

    def _draw_seir_graph(self, surface: pygame.Surface, history: list[dict]) -> None:
        """S-E-I-R Compartmental Model Trajectories"""
        pygame.draw.rect(surface, theme.PANEL_BG_RAISED, self.seir_graph_rect, border_radius=10)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.seir_graph_rect, width=1, border_radius=10)

        # Title
        graph_title = self.font.render("S-E-I-R Compartmental Dynamics", True, theme.TEXT_PRIMARY)
        surface.blit(graph_title, (self.seir_graph_rect.x + 12, self.seir_graph_rect.y + 8))

        if len(history) < 2:
            return

        # Extract time series
        ticks = [h["tick"] for h in history]
        max_tick = max(ticks)
        max_pop = max(h["population"] for h in history)

        # Graph bounds
        gx, gy, gw, gh = (
            self.seir_graph_rect.x + 50,
            self.seir_graph_rect.y + 35,
            self.seir_graph_rect.width - 70,
            self.seir_graph_rect.height - 55
        )

        # Axes
        pygame.draw.line(surface, theme.PANEL_BORDER_BRIGHT, (gx, gy), (gx, gy + gh), 1)
        pygame.draw.line(surface, theme.PANEL_BORDER_BRIGHT, (gx, gy + gh), (gx + gw, gy + gh), 1)

        # Y-axis labels
        for i in range(5):
            frac = i / 4.0
            val = int(max_pop * frac)
            py = int(gy + gh - frac * gh)
            label = self.font.render(f"{val:,}", True, theme.TEXT_MUTED)
            surface.blit(label, (gx - label.get_width() - 6, py - label.get_height() // 2))
            pygame.draw.line(surface, (40, 50, 70), (gx, py), (gx + gw, py), 1)

        # Plot lines: S (blue), E (purple), I (red), R (green)
        def project(tick, value):
            px = gx + int((tick / max(1, max_tick)) * gw)
            py = gy + gh - int((value / max(1, max_pop)) * gh)
            return (px, py)

        lines = {
            "susceptible": (theme.REGION_LOW, []),
            "exposed": (theme.COLOR_EXPOSED, []),
            "believing": (theme.COLOR_BELIEF, []),
            "skeptical": (theme.COLOR_CURE, []),
        }

        for h in history:
            for key in lines:
                lines[key][1].append(project(h["tick"], h[key]))

        for key, (color, points) in lines.items():
            if len(points) > 1:
                pygame.draw.lines(surface, color, False, points, 2)

        # Legend
        legend_x = gx + gw - 300
        legend_y = gy + 10
        legend_items = [
            ("S - Susceptible", theme.REGION_LOW),
            ("E - Exposed", theme.COLOR_EXPOSED),
            ("I - Believing", theme.COLOR_BELIEF),
            ("R - Skeptical", theme.COLOR_CURE),
        ]
        for i, (label, color) in enumerate(legend_items):
            lx = legend_x + (i % 2) * 150
            ly = legend_y + (i // 2) * 18
            pygame.draw.rect(surface, color, (lx, ly + 3, 10, 10))
            txt = self.font.render(label, True, theme.TEXT_SECONDARY)
            surface.blit(txt, (lx + 14, ly))

    def _draw_rt_graph(self, surface: pygame.Surface, history: list[dict]) -> None:
        """R_t Effective Reproduction Number Tracking"""
        pygame.draw.rect(surface, theme.PANEL_BG_RAISED, self.rt_graph_rect, border_radius=10)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rt_graph_rect, width=1, border_radius=10)

        # Title
        graph_title = self.font.render("R_t Effective Reproduction Number (Epidemic Threshold = 1.0)",
                                      True, theme.TEXT_PRIMARY)
        surface.blit(graph_title, (self.rt_graph_rect.x + 12, self.rt_graph_rect.y + 8))

        if len(history) < 2:
            return

        # Extract R_t series. Entries are None while the estimator does not yet
        # have enough history to produce a meaningful number (the first tick or
        # two of any run, and the first few ticks of SEIR runs, where the
        # generation-time mass has not yet been covered), so they are excluded
        # from the axis scaling rather than being treated as zero.
        ticks = [h["tick"] for h in history]
        max_tick = max(ticks)
        rt_values = [h["r_t"] for h in history if h["r_t"] is not None]
        # Floor the axis at 3.0 so the R_t = 1.0 threshold line stays legible,
        # but never below the data -- scaling to the observed peak keeps the
        # whole curve on screen. (A true floor, not the no-op this line used to
        # be: with the old beta/gamma placeholder R_t reached 150, so max()
        # always returned the outlier and the threshold line rendered at
        # 0.7% of the graph height.)
        max_rt = max(3.0, max(rt_values)) if rt_values else 3.0

        # Graph bounds
        gx, gy, gw, gh = (
            self.rt_graph_rect.x + 50,
            self.rt_graph_rect.y + 35,
            self.rt_graph_rect.width - 70,
            self.rt_graph_rect.height - 55
        )

        # Axes
        pygame.draw.line(surface, theme.PANEL_BORDER_BRIGHT, (gx, gy), (gx, gy + gh), 1)
        pygame.draw.line(surface, theme.PANEL_BORDER_BRIGHT, (gx, gy + gh), (gx + gw, gy + gh), 1)

        # Y-axis labels
        for i in range(5):
            frac = i / 4.0
            val = max_rt * frac
            py = int(gy + gh - frac * gh)
            label = self.font.render(f"{val:.1f}", True, theme.TEXT_MUTED)
            surface.blit(label, (gx - label.get_width() - 6, py - label.get_height() // 2))
            pygame.draw.line(surface, (40, 50, 70), (gx, py), (gx + gw, py), 1)

        # Epidemic threshold line R_t = 1.0
        threshold_y = gy + gh - int((1.0 / max_rt) * gh)
        pygame.draw.line(surface, theme.COLOR_WARNING, (gx, threshold_y), (gx + gw, threshold_y), 2)
        threshold_label = self.font.render("R_t = 1.0 (Threshold)", True, theme.COLOR_WARNING)
        surface.blit(threshold_label, (gx + gw - threshold_label.get_width() - 10, threshold_y - 20))

        # Plot R_t curve, skipping ticks whose estimate is undefined and
        # breaking the line across them so it does not visually bridge a gap.
        segments: list[list[tuple[int, int]]] = []
        current_segment: list[tuple[int, int]] = []
        for h in history:
            if h["r_t"] is None:
                if len(current_segment) > 1:
                    segments.append(current_segment)
                current_segment = []
                continue
            px = gx + int((h["tick"] / max(1, max_tick)) * gw)
            py = gy + gh - int((min(h["r_t"], max_rt) / max_rt) * gh)
            current_segment.append((px, py))
        if len(current_segment) > 1:
            segments.append(current_segment)

        for points in segments:
            pygame.draw.lines(surface, theme.ACCENT_BRIGHT, False, points, 3)

        # Current R_t indicator
        current_rt = history[-1]["r_t"]
        if current_rt is None:
            current_text = self.font.render(
                "Current R_t: warming up", True, theme.TEXT_MUTED
            )
        else:
            current_color = theme.COLOR_DANGER if current_rt > 1.0 else theme.COLOR_CURE
            current_text = self.font.render(f"Current R_t: {current_rt:.2f}", True, current_color)
        surface.blit(current_text, (gx + 10, gy + 10))

        # Phase annotations
        countermeasure_tick = next((h["tick"] for h in history if h["counter_active"]), None)
        if countermeasure_tick is not None:
            phase_x = gx + int((countermeasure_tick / max(1, max_tick)) * gw)
            pygame.draw.line(surface, theme.ACCENT_DIM, (phase_x, gy), (phase_x, gy + gh), 1)
            phase_label = self.font.render("Countermeasure Active", True, theme.ACCENT_DIM)
            surface.blit(phase_label, (phase_x + 4, gy + 5))
