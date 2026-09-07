"""
UI Effects & Animation Engine for TIPS-G Desktop Frontend.
Provides hardware-accelerated slide & cross-fade page transitions,
smooth number roll-up animations, biometric HUD laser scanning,
pulsing status badges, and asynchronous model warm-up.
"""

import math
import time
from typing import Optional
from PyQt6.QtCore import (
    Qt, QObject, QThread, QTimer, QPropertyAnimation, 
    QParallelAnimationGroup, QEasingCurve, QPoint, QRect, QRectF, pyqtSignal, pyqtProperty
)
from PyQt6.QtWidgets import (
    QWidget, QStackedWidget, QGraphicsOpacityEffect, 
    QLabel, QVBoxLayout, QHBoxLayout, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QLinearGradient, 
    QPainterPath, QPixmap, QImage, QRadialGradient
)
from loguru import logger


class AmbientWaveBackground(QWidget):
    """An ambient animated background widget with soft glowing gradient waves."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(40)  # ~25 FPS ambient

    def _animate(self):
        self._phase = (self._phase + 0.03) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Dynamic floating ambient light orbs
        orb1_x = int(w * 0.2 + w * 0.1 * math.sin(self._phase))
        orb1_y = int(h * 0.3 + h * 0.08 * math.cos(self._phase))
        
        grad1 = QRadialGradient(orb1_x, orb1_y, int(w * 0.35))
        grad1.setColorAt(0.0, QColor(59, 130, 246, 22))
        grad1.setColorAt(1.0, QColor(59, 130, 246, 0))
        painter.fillRect(self.rect(), QBrush(grad1))

        orb2_x = int(w * 0.8 - w * 0.1 * math.cos(self._phase * 0.8))
        orb2_y = int(h * 0.7 - h * 0.08 * math.sin(self._phase * 0.8))
        
        grad2 = QRadialGradient(orb2_x, orb2_y, int(w * 0.4))
        grad2.setColorAt(0.0, QColor(14, 165, 233, 18))
        grad2.setColorAt(1.0, QColor(14, 165, 233, 0))
        painter.fillRect(self.rect(), QBrush(grad2))


class AnimatedStackedWidget(QStackedWidget):
    """A high-performance QStackedWidget with smooth 60 FPS slide & cross-fade page transitions."""

    def __init__(self, parent=None, duration: int = 280):
        super().__init__(parent)
        self.duration = duration
        self._is_animating = False
        self._anim_group = None

    def setCurrentIndex(self, index: int):
        if index == self.currentIndex() or index < 0 or index >= self.count():
            return

        if self._is_animating and self._anim_group:
            self._anim_group.stop()
            self._is_animating = False

        current_widget = self.currentWidget()
        next_widget = self.widget(index)

        if not current_widget or not next_widget:
            super().setCurrentIndex(index)
            return

        self._is_animating = True

        # Setup opacity effect on next widget
        next_effect = QGraphicsOpacityEffect(next_widget)
        next_widget.setGraphicsEffect(next_effect)
        next_effect.setOpacity(0.0)

        # Show next widget and bring to front
        super().setCurrentIndex(index)
        next_widget.show()
        next_widget.raise_()

        # Parallel Animation: Slide Up + Fade In
        self._anim_group = QParallelAnimationGroup(self)

        # 1. Opacity Fade
        fade_anim = QPropertyAnimation(next_effect, b"opacity")
        fade_anim.setDuration(self.duration)
        fade_anim.setStartValue(0.0)
        fade_anim.setEndValue(1.0)
        fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_group.addAnimation(fade_anim)

        # 2. Position Slide Up (by 24px)
        orig_pos = next_widget.pos()
        slide_anim = QPropertyAnimation(next_widget, b"pos")
        slide_anim.setDuration(self.duration)
        slide_anim.setStartValue(QPoint(orig_pos.x(), orig_pos.y() + 24))
        slide_anim.setEndValue(orig_pos)
        slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_group.addAnimation(slide_anim)

        def on_finished():
            next_widget.setGraphicsEffect(None)
            next_widget.move(orig_pos)
            self._is_animating = False

        self._anim_group.finished.connect(on_finished)
        self._anim_group.start()


class AnimatedStatLabel(QLabel):
    """A QLabel that animates numbers counting up smoothly from 0 to the target value."""

    def __init__(self, text="0", parent=None):
        super().__init__(text, parent)
        self._current_val = 0
        self._target_val = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step_number)

    def set_animated_value(self, target, duration_ms: int = 500):
        try:
            target_int = int(target)
        except Exception:
            self.setText(str(target))
            return
        
        self._target_val = target_int
        if self._current_val == self._target_val:
            self.setText(str(self._target_val))
            return
            
        self._start_val = self._current_val
        self._start_time = time.perf_counter()
        self._duration = max(0.2, duration_ms / 1000.0)
        self._timer.start(16)  # ~60 FPS update

    def _step_number(self):
        elapsed = time.perf_counter() - self._start_time
        progress = min(1.0, elapsed / self._duration)
        # Ease out cubic curve
        ease = 1.0 - math.pow(1.0 - progress, 3)
        current = int(self._start_val + (self._target_val - self._start_val) * ease)
        self._current_val = current
        self.setText(str(current))
        if progress >= 1.0:
            self._current_val = self._target_val
            self.setText(str(self._target_val))
            self._timer.stop()


class PulsingBadge(QWidget):
    """A modern glowing badge with a soft breathing pulse animation."""

    def __init__(self, parent=None, color: QColor = QColor(239, 68, 68), text: str = ""):
        super().__init__(parent)
        self._color = color
        self._text = text
        self._glow_radius = 4.0
        self._alpha = 255
        self.setFixedSize(24, 24)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_pulse)
        self._pulse_step = 0.0
        self._timer.start(35)

    def _update_pulse(self):
        self._pulse_step += 0.09
        self._glow_radius = 3.5 + 3.0 * math.sin(self._pulse_step)
        self.update()

    def set_text(self, text: str):
        self._text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        base_radius = 5.5

        # Outer soft glow ring
        glow_color = QColor(self._color)
        glow_color.setAlpha(int(70 + 50 * math.sin(self._pulse_step)))
        painter.setBrush(QBrush(glow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(base_radius + self._glow_radius), int(base_radius + self._glow_radius))

        # Core dot
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(base_radius), int(base_radius))

        # Center text if any
        if self._text:
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Inter", 8, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)


class BiometricScanOverlay:
    """Renders dynamic laser scan lines, glowing radar reticles, and target corner brackets."""

    def __init__(self):
        self.scan_pos = 0.0  # 0.0 to 1.0
        self.scan_dir = 1.0
        self.pulse_phase = 0.0
        self.radar_angle = 0.0
        self.last_update = time.perf_counter()

    def update(self):
        now = time.perf_counter()
        dt = min(now - self.last_update, 0.1)
        self.last_update = now

        # Update laser scan bar position (smooth triangle wave)
        speed = 0.55
        self.scan_pos += self.scan_dir * speed * dt
        if self.scan_pos >= 1.0:
            self.scan_pos = 1.0
            self.scan_dir = -1.0
        elif self.scan_pos <= 0.0:
            self.scan_pos = 0.0
            self.scan_dir = 1.0

        self.pulse_phase = (self.pulse_phase + 3.5 * dt) % (2 * math.pi)
        self.radar_angle = (self.radar_angle + 120.0 * dt) % 360.0

    def draw_hud(self, painter: QPainter, width: int, height: int, face_box: Optional[tuple] = None, is_verified: bool = False, label: str = ""):
        """Draws the state-of-the-art biometric scanner HUD on top of the camera frame."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Animated Laser Scan Bar
        scan_y = int(self.scan_pos * height)
        laser_color = QColor(16, 185, 129) if is_verified else QColor(14, 165, 233)

        # Laser beam glowing gradient
        grad = QLinearGradient(0, scan_y - 16, 0, scan_y + 16)
        top_c = QColor(laser_color)
        top_c.setAlpha(0)
        mid_c = QColor(laser_color)
        mid_c.setAlpha(220)
        bot_c = QColor(laser_color)
        bot_c.setAlpha(0)
        grad.setColorAt(0.0, top_c)
        grad.setColorAt(0.5, mid_c)
        grad.setColorAt(1.0, bot_c)

        painter.fillRect(0, scan_y - 16, width, 32, QBrush(grad))

        # Bright center laser line
        line_pen = QPen(QColor(255, 255, 255, 240), 2)
        painter.setPen(line_pen)
        painter.drawLine(0, scan_y, width, scan_y)

        # 2. Target Corner Brackets & Box
        if face_box:
            x, y, w, h = face_box
            box_color = QColor(16, 185, 129) if is_verified else QColor(56, 189, 248)
            
            # Pulsing semi-transparent box fill
            fill_color = QColor(box_color)
            fill_color.setAlpha(int(24 + 18 * math.sin(self.pulse_phase)))
            painter.fillRect(x, y, w, h, QBrush(fill_color))

            # Target brackets (corners)
            bracket_len = min(30, w // 4, h // 4)
            pen = QPen(box_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

            # Top-Left
            painter.drawLine(x, y, x + bracket_len, y)
            painter.drawLine(x, y, x, y + bracket_len)
            # Top-Right
            painter.drawLine(x + w, y, x + w - bracket_len, y)
            painter.drawLine(x + w, y, x + w, y + bracket_len)
            # Bottom-Left
            painter.drawLine(x, y + h, x + bracket_len, y + h)
            painter.drawLine(x, y, x, y + h - bracket_len)
            # Bottom-Right
            painter.drawLine(x + w, y + h, x + w - bracket_len, y + h)
            painter.drawLine(x + w, y + h, x + w, y + h - bracket_len)

            # Center target crosshair
            cx, cy = x + w // 2, y + h // 2
            cross_pen = QPen(QColor(255, 255, 255, 140), 1)
            painter.setPen(cross_pen)
            painter.drawLine(cx - 14, cy, cx + 14, cy)
            painter.drawLine(cx, cy - 14, cx, cy + 14)

            # Label badge
            if label:
                painter.setFont(QFont("Inter", 10, QFont.Weight.Bold))
                text_rect = QRect(x, max(0, y - 30), w, 26)
                badge_bg = QColor(15, 23, 42, 230)
                painter.fillRect(text_rect, QBrush(badge_bg))
                painter.setPen(QColor(56, 189, 248) if not is_verified else QColor(52, 211, 153))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)


class NotificationToast(QFrame):
    """A floating, animated in-app toast card that glides down from the top."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NotificationToast")
        self.setFixedHeight(56)
        self.setMinimumWidth(340)
        self.setStyleSheet("""
            #NotificationToast {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e293b);
                border: 1.5px solid rgba(56, 189, 248, 0.5);
                border-radius: 14px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(12)

        self.icon_label = QLabel("✨")
        self.icon_label.setStyleSheet("font-size: 20px;")
        layout.addWidget(self.icon_label)

        self.msg_label = QLabel("")
        self.msg_label.setStyleSheet("color: #f8fafc; font-weight: 700; font-size: 13px; font-family: 'Segoe UI', system-ui, sans-serif;")
        layout.addWidget(self.msg_label, stretch=1)

        self.hide()
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide_animated)

    def show_message(self, message: str, icon: str = "✓", duration_ms: int = 3800, is_success: bool = True):
        self.msg_label.setText(message)
        self.icon_label.setText(icon)
        if is_success:
            self.setStyleSheet("""
                #NotificationToast {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #064e3b, stop:1 #0f766e);
                    border: 1.5px solid rgba(52, 211, 153, 0.7);
                    border-radius: 14px;
                }
            """)
        else:
            self.setStyleSheet("""
                #NotificationToast {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7f1d1d, stop:1 #991b1b);
                    border: 1.5px solid rgba(248, 113, 113, 0.7);
                    border-radius: 14px;
                }
            """)

        self.adjustSize()
        if self.parent():
            parent_w = self.parent().width()
            toast_w = max(self.width(), 340)
            self.setGeometry((parent_w - toast_w) // 2, 20, toast_w, 56)

        self.show()
        self.raise_()

        # Slide-down animation
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(300)
        current_x = self.x()
        self.anim.setStartValue(QPoint(current_x, -70))
        self.anim.setEndValue(QPoint(current_x, 26))
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.anim.start()

        self._dismiss_timer.start(duration_ms)

    def hide_animated(self):
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(250)
        current_x = self.x()
        self.anim.setStartValue(QPoint(current_x, 26))
        self.anim.setEndValue(QPoint(current_x, -80))
        self.anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim.finished.connect(self.hide)
        self.anim.start()


class AsyncModelWarmupWorker(QThread):
    """Background worker that warms up ArcFace ONNX and face recognition models asynchronously."""
    warmup_complete = pyqtSignal(bool)

    def run(self):
        try:
            logger.info("[WARMUP] Starting asynchronous AI facial model warm-up in background thread...")
            from frontend.onnx_face_service import onnx_face_service
            onnx_face_service.load_models()
            logger.info("[WARMUP] AI facial models successfully warmed up and ready in memory.")
            self.warmup_complete.emit(True)
        except Exception as e:
            logger.warning(f"[WARMUP] Async model warm-up note: {e}")
            self.warmup_complete.emit(False)
