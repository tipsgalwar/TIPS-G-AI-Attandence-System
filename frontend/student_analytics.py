"""
TIPS-G ALWAR - Student Attendance Analytics & Biometric Heatmap Component.
Refined Neumorphic Soft-UI Design System matching the native desktop theme.
"""

import os
import calendar
from datetime import datetime, date
from typing import Optional, Dict, List
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSize, QRect, QPoint, QRectF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, 
    QGridLayout, QScrollArea, QSizePolicy, QToolTip, QDialog
)
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QCursor
from loguru import logger

try:
    from frontend.api_client import api_client
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from frontend.api_client import api_client


class StudentAnalyticsDataLoader(QThread):
    """Background asynchronous loader for student current month attendance analytics."""
    data_loaded = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, student_id: Optional[int] = None):
        super().__init__()
        self.student_id = student_id
        now = datetime.now()
        self.month = now.month
        self.year = now.year

    def run(self):
        try:
            res = api_client.get_student_monthly_analytics(
                student_id=self.student_id,
                month=self.month,
                year=self.year
            )
            self.data_loaded.emit(res or {})
        except Exception as e:
            logger.error(f"Failed to fetch student current month analytics async: {e}")
            self.error_occurred.emit(str(e))


class CalendarDayTile(QFrame):
    """
    Neumorphic Calendar Heatmap Day Tile for Current Month.
    """
    def __init__(self, day_num: Optional[int], day_data: Optional[dict], is_today: bool = False, parent=None):
        super().__init__(parent)
        self.day_num = day_num
        self.day_data = day_data or {}
        self.is_today = is_today
        self.init_ui()

    def init_ui(self):
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        if not self.day_num:
            self.setStyleSheet("""
                QFrame {
                    background-color: transparent;
                    border: 1px dashed #cbd5e1;
                    border-radius: 10px;
                }
            """)
            return

        status = str(self.day_data.get("status", "Upcoming")).capitalize()
        check_in = self.day_data.get("check_in")
        check_out = self.day_data.get("check_out")
        holiday_name = self.day_data.get("holiday_name", "")

        # Top row: Day Number + Status Badge
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        
        day_lbl = QLabel(str(self.day_num))
        day_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #1e293b; background: transparent; border: none;")
        top_row.addWidget(day_lbl)

        if self.is_today:
            today_badge = QLabel("TODAY")
            today_badge.setStyleSheet("""
                font-size: 8px; font-weight: 800; background: #2563eb; color: #ffffff;
                padding: 1px 5px; border-radius: 4px; border: none;
            """)
            top_row.addWidget(today_badge)

        top_row.addStretch()
        layout.addLayout(top_row)

        # Status subtitle / time pill
        status_lbl = QLabel()
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if status == "Present":
            bg_color = "#e6f9f0"
            border_color = "#10b981"
            txt_color = "#047857"
            time_txt = f"✓ {check_in}" if check_in else "✓ Present"
            status_lbl.setText(time_txt)
            status_lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {txt_color}; border: none; background: transparent;")
            self.setToolTip(f"<b>Present</b><br/>Check-in: {check_in or 'Recorded'}<br/>Check-out: {check_out or '—'}")
        elif status == "Late":
            bg_color = "#fef9e7"
            border_color = "#f59e0b"
            txt_color = "#b45309"
            time_txt = f"⏱ {check_in}" if check_in else "⏱ Late"
            status_lbl.setText(time_txt)
            status_lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {txt_color}; border: none; background: transparent;")
            self.setToolTip(f"<b>Late Arrival</b><br/>Check-in: {check_in or 'Recorded'}<br/>Check-out: {check_out or '—'}")
        elif status == "Absent":
            bg_color = "#fef2f2"
            border_color = "#ef4444"
            txt_color = "#b91c1c"
            status_lbl.setText("✗ Absent")
            status_lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {txt_color}; border: none; background: transparent;")
            self.setToolTip("<b>Absent</b><br/>No biometric check-in recorded.")
        elif status == "Leave":
            bg_color = "#f5f3ff"
            border_color = "#8b5cf6"
            txt_color = "#6d28d9"
            status_lbl.setText("🏖 Leave")
            status_lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {txt_color}; border: none; background: transparent;")
            self.setToolTip("<b>Approved Leave</b><br/>Leave application verified.")
        elif status == "Holiday":
            bg_color = "#edf2f7"
            border_color = "#94a3b8"
            txt_color = "#475569"
            short_h = holiday_name[:12] + ".." if len(holiday_name) > 12 else (holiday_name or "Holiday")
            status_lbl.setText(f"🎉 {short_h}")
            status_lbl.setStyleSheet(f"font-size: 9px; font-weight: 600; color: {txt_color}; border: none; background: transparent;")
            self.setToolTip(f"<b>Official Holiday</b><br/>{holiday_name or 'Holiday'}")
        elif status == "Weekend":
            bg_color = "#edf2f7"
            border_color = "#cbd5e1"
            txt_color = "#94a3b8"
            weekend_name = self.day_data.get("weekend_label") or "Weekend"
            status_lbl.setText(weekend_name)
            status_lbl.setStyleSheet(f"font-size: 10px; color: {txt_color}; border: none; background: transparent;")
            self.setToolTip(f"<b>{weekend_name}</b><br/>Academic Weekend Off")
        else: # Upcoming or Unrecorded
            bg_color = "#e8edf5"
            border_color = "#cbd5e1"
            txt_color = "#94a3b8"
            status_lbl.setText("—")
            status_lbl.setStyleSheet(f"font-size: 10px; color: {txt_color}; border: none; background: transparent;")
            self.setToolTip("Upcoming class day")

        layout.addWidget(status_lbl)

        today_ring = "border: 2px solid #2563eb;" if self.is_today else "border: 1px solid #ffffff; border-bottom: 2px solid #cbd5e1; border-right: 2px solid #cbd5e1;"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                {today_ring}
                border-left: 4px solid {border_color};
                border-radius: 10px;
            }}
            QFrame:hover {{
                border-color: {border_color};
                background-color: #ffffff;
            }}
        """)


class StudentAttendanceAnalyticsWidget(QWidget):
    """
    Student Current Month Attendance Analytics & Heatmap Component.
    Styled with the TIPS-G Neumorphic (Soft UI) Design System.
    """
    def __init__(self, student_id: Optional[int] = None, user_info: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.student_id = student_id
        self.user_info = user_info or {}
        
        now = datetime.now()
        self.current_month = now.month
        self.current_year = now.year
        self.today_date = now.date()

        self.current_analytics = {}
        self.init_ui()
        self.load_analytics_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        # ── 1. Top Neumorphic Header & Today's Marked Attendance Status ──────
        nav_header = QFrame()
        nav_header.setStyleSheet("""
            QFrame {
                background-color: #e8edf5;
                border: 1.5px solid #ffffff;
                border-bottom: 2px solid #cbd5e1;
                border-right: 2px solid #cbd5e1;
                border-radius: 14px;
                padding: 10px 18px;
            }
        """)
        nav_layout = QHBoxLayout(nav_header)
        nav_layout.setContentsMargins(10, 6, 10, 6)
        nav_layout.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        month_name = calendar.month_name[self.current_month]
        h_title = QLabel(f"📅 {month_name} {self.current_year} Attendance Heatmap")
        h_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #1e3a8a; border: none; background: transparent;")
        
        self.today_status_banner = QLabel("Today's Status: Checking...")
        self.today_status_banner.setStyleSheet("font-size: 12px; font-weight: 700; color: #475569; border: none; background: transparent;")
        
        title_box.addWidget(h_title)
        title_box.addWidget(self.today_status_banner)
        nav_layout.addLayout(title_box)

        nav_layout.addStretch()

        # Status Tag Pill
        self.status_tag_pill = QLabel("STATUS: LIVE")
        self.status_tag_pill.setStyleSheet("""
            font-size: 11px; font-weight: 800; background-color: #dbeafe; color: #1e40af;
            padding: 5px 12px; border-radius: 8px; border: 1px solid #bfdbfe;
        """)
        nav_layout.addWidget(self.status_tag_pill)

        refresh_btn = QPushButton("🔄 Refresh Live Records")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: #ffffff; font-weight: 700; font-size: 12px;
                padding: 8px 18px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        refresh_btn.clicked.connect(self.load_analytics_data)
        nav_layout.addWidget(refresh_btn)

        main_layout.addWidget(nav_header)

        # ── 2. Metric Overview Stat Cards (Neumorphic) ──────────────────────
        stats_grid = QHBoxLayout()
        stats_grid.setSpacing(14)

        self.card_pct = self._create_metric_card("Attendance Rate", "0.0%", "#10b981", "Criteria: 75%")
        self.card_present = self._create_metric_card("Present Days", "0", "#059669", "On-Time Check-ins")
        self.card_late = self._create_metric_card("Late Arrivals", "0", "#f59e0b", "Grace Check-ins")
        self.card_absent = self._create_metric_card("Absences", "0", "#ef4444", "Unrecorded Absences")
        self.card_leaves = self._create_metric_card("Approved Leaves", "0", "#8b5cf6", "Verified Leaves")
        self.card_working = self._create_metric_card("Working Days", "0", "#3b82f6", "Scheduled Days")

        stats_grid.addWidget(self.card_pct)
        stats_grid.addWidget(self.card_present)
        stats_grid.addWidget(self.card_late)
        stats_grid.addWidget(self.card_absent)
        stats_grid.addWidget(self.card_leaves)
        stats_grid.addWidget(self.card_working)

        main_layout.addLayout(stats_grid)

        # ── 3. Calendar Attendance Heatmap Card (Neumorphic) ────────────────
        heatmap_card = QFrame()
        heatmap_card.setStyleSheet("""
            QFrame#HeatmapCard {
                background-color: #e8edf5;
                border: 1.5px solid #ffffff;
                border-bottom: 2px solid #cbd5e1;
                border-right: 2px solid #cbd5e1;
                border-radius: 16px;
                padding: 16px;
            }
        """)
        heatmap_card.setObjectName("HeatmapCard")
        heatmap_layout = QVBoxLayout(heatmap_card)
        heatmap_layout.setContentsMargins(16, 14, 16, 14)
        heatmap_layout.setSpacing(12)

        heat_hdr = QHBoxLayout()
        heat_title = QLabel(f"🗓️ {month_name} {self.current_year} Biometric Attendance Matrix")
        heat_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #1e3a8a; border: none; background: transparent;")
        heat_hdr.addWidget(heat_title)
        heat_hdr.addStretch()

        self.eligibility_badge = QLabel("ELIGIBILITY: CALCULATING...")
        self.eligibility_badge.setStyleSheet("""
            font-size: 11px; font-weight: 800; background-color: #dcfce7; color: #166534;
            padding: 4px 12px; border-radius: 6px; border: 1px solid #bbf7d0;
        """)
        heat_hdr.addWidget(self.eligibility_badge)
        heatmap_layout.addLayout(heat_hdr)

        # Weekdays header row (Mon - Sun)
        days_row = QHBoxLayout()
        days_row.setSpacing(8)
        weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        for day_name in weekdays:
            d_lbl = QLabel(day_name)
            d_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d_lbl.setStyleSheet("""
                font-size: 11px; font-weight: 800; color: #64748b;
                padding: 6px 0px; background-color: #e8edf5;
                border: 1px solid #ffffff; border-bottom: 1.5px solid #cbd5e1;
                border-radius: 6px;
            """)
            days_row.addWidget(d_lbl)
        heatmap_layout.addLayout(days_row)

        # Calendar 7-column Grid Container
        self.calendar_grid_layout = QGridLayout()
        self.calendar_grid_layout.setSpacing(8)
        heatmap_layout.addLayout(self.calendar_grid_layout)

        # Heatmap Color Legend
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(14)
        legend_layout.addStretch()

        legend_items = [
            ("Present (On-time)", "#10b981", "#e6f9f0"),
            ("Late Arrival", "#f59e0b", "#fef9e7"),
            ("Absent", "#ef4444", "#fef2f2"),
            ("Approved Leave", "#8b5cf6", "#f5f3ff"),
            ("Sunday / Holiday", "#94a3b8", "#edf2f7"),
        ]
        for name, border_col, bg_col in legend_items:
            dot = QLabel(f"  {name}")
            dot.setStyleSheet(f"""
                font-size: 11px; font-weight: 600; color: #334155;
                background-color: {bg_col}; border: 1px solid #cbd5e1; border-left: 4px solid {border_col};
                border-radius: 6px; padding: 3px 10px;
            """)
            legend_layout.addWidget(dot)

        legend_layout.addStretch()
        heatmap_layout.addLayout(legend_layout)
        main_layout.addWidget(heatmap_card)

    def _create_metric_card(self, title: str, init_val: str, color: str, subtitle: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #e8edf5;
                border: 1.5px solid #ffffff;
                border-bottom: 2px solid #cbd5e1;
                border-right: 2px solid #cbd5e1;
                border-top: 3.5px solid {color};
                border-radius: 14px;
                padding: 10px;
            }}
            QFrame:hover {{
                background-color: #edf2f9;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        val_lbl = QLabel(init_val)
        val_lbl.setObjectName("ValLabel")
        val_lbl.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {color}; border: none; background: transparent;")
        
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155; border: none; background: transparent;")

        s_lbl = QLabel(subtitle)
        s_lbl.setStyleSheet("font-size: 10px; color: #64748b; border: none; background: transparent;")

        layout.addWidget(val_lbl)
        layout.addWidget(t_lbl)
        layout.addWidget(s_lbl)
        return card

    def load_analytics_data(self):
        """Dispatches async worker to load current month telemetry and render calendar."""
        target_sid = self.student_id or self.user_info.get("id")
        self.loader = StudentAnalyticsDataLoader(student_id=target_sid)
        self.loader.data_loaded.connect(self.populate_analytics_ui)
        self.loader.start()

    @pyqtSlot(dict)
    def populate_analytics_ui(self, data: dict):
        self.current_analytics = data or {}
        pct = float(data.get("percentage", 100.0))
        present_cnt = data.get("present_count", 0)
        late_cnt = data.get("late_count", 0)
        absent_cnt = data.get("absent_count", 0)
        leave_cnt = data.get("leave_count", 0)
        working_days = data.get("total_working_days", 0)
        daily_map = data.get("daily_map", {})

        # Update metric cards
        pct_color = "#10b981" if pct >= 75.0 else "#ef4444"
        self.card_pct.findChild(QLabel, "ValLabel").setText(f"{pct:.1f}%")
        self.card_pct.findChild(QLabel, "ValLabel").setStyleSheet(f"font-size: 22px; font-weight: 800; color: {pct_color}; border: none; background: transparent;")
        
        self.card_present.findChild(QLabel, "ValLabel").setText(str(present_cnt))
        self.card_late.findChild(QLabel, "ValLabel").setText(str(late_cnt))
        self.card_absent.findChild(QLabel, "ValLabel").setText(str(absent_cnt))
        self.card_leaves.findChild(QLabel, "ValLabel").setText(str(leave_cnt))
        self.card_working.findChild(QLabel, "ValLabel").setText(str(working_days))

        # Check today's marked attendance status
        today_key = f"{self.today_date.year:04d}-{self.today_date.month:02d}-{self.today_date.day:02d}"
        today_data = daily_map.get(today_key, {})
        t_status = str(today_data.get("status", "")).capitalize()
        t_check_in = today_data.get("check_in")

        if t_status in ["Present", "Late"]:
            t_msg = f"Today's Attendance:  ✅ MARKED ({t_status} at {t_check_in or 'Live Scan'})"
            self.today_status_banner.setText(t_msg)
            self.today_status_banner.setStyleSheet("font-size: 12px; font-weight: 800; color: #047857; border: none; background: transparent;")
            self.status_tag_pill.setText("✓ MARKED TODAY")
            self.status_tag_pill.setStyleSheet("""
                font-size: 11px; font-weight: 800; background-color: #d1fae5; color: #065f46;
                padding: 5px 12px; border-radius: 8px; border: 1px solid #6ee7b7;
            """)
        elif t_status == "Leave":
            self.today_status_banner.setText("Today's Attendance:  🏖 On Approved Leave")
            self.today_status_banner.setStyleSheet("font-size: 12px; font-weight: 800; color: #6d28d9; border: none; background: transparent;")
            self.status_tag_pill.setText("🏖 APPROVED LEAVE")
            self.status_tag_pill.setStyleSheet("""
                font-size: 11px; font-weight: 800; background-color: #ede9fe; color: #5b21b6;
                padding: 5px 12px; border-radius: 8px; border: 1px solid #c4b5fd;
            """)
        elif t_status == "Holiday":
            h_name = today_data.get("holiday_name", "Official Holiday")
            self.today_status_banner.setText(f"Today's Attendance:  🎉 College Holiday ({h_name})")
            self.today_status_banner.setStyleSheet("font-size: 12px; font-weight: 800; color: #475569; border: none; background: transparent;")
            self.status_tag_pill.setText("🎉 HOLIDAY")
            self.status_tag_pill.setStyleSheet("""
                font-size: 11px; font-weight: 800; background-color: #f1f5f9; color: #334155;
                padding: 5px 12px; border-radius: 8px; border: 1px solid #cbd5e1;
            """)
        elif self.today_date.weekday() in [5, 6]:
            w_day_name = "Saturday" if self.today_date.weekday() == 5 else "Sunday"
            self.today_status_banner.setText(f"Today's Attendance:  {w_day_name} (Academic Weekend Off)")
            self.today_status_banner.setStyleSheet("font-size: 12px; font-weight: 700; color: #64748b; border: none; background: transparent;")
            self.status_tag_pill.setText(f"{w_day_name.upper()} OFF")
            self.status_tag_pill.setStyleSheet("""
                font-size: 11px; font-weight: 800; background-color: #f1f5f9; color: #475569;
                padding: 5px 12px; border-radius: 8px; border: 1px solid #cbd5e1;
            """)
        else:
            self.today_status_banner.setText("Today's Attendance:  ⏳ NOT MARKED YET (Go to Face Attendance to check in)")
            self.today_status_banner.setStyleSheet("font-size: 12px; font-weight: 800; color: #b45309; border: none; background: transparent;")
            self.status_tag_pill.setText("⏳ PENDING CHECK-IN")
            self.status_tag_pill.setStyleSheet("""
                font-size: 11px; font-weight: 800; background-color: #fef3c7; color: #92400e;
                padding: 5px 12px; border-radius: 8px; border: 1px solid #fcd34d;
            """)

        # Update Eligibility Badge
        if pct >= 75.0:
            self.eligibility_badge.setText(f"✓ ELIGIBLE FOR SEMESTER EXAMINATIONS ({pct:.1f}%)")
            self.eligibility_badge.setStyleSheet("""
                font-size: 11px; font-weight: 800; background-color: #dcfce7; color: #166534;
                padding: 4px 12px; border-radius: 6px; border: 1px solid #bbf7d0;
            """)
        else:
            self.eligibility_badge.setText(f"⚠ ATTENDANCE SHORTAGE DEFICIT ({pct:.1f}% < 75%)")
            self.eligibility_badge.setStyleSheet("""
                font-size: 11px; font-weight: 800; background-color: #fee2e2; color: #991b1b;
                padding: 4px 12px; border-radius: 6px; border: 1px solid #fca5a5;
            """)

        # Render Heatmap Calendar Grid for Current Month
        self._render_calendar_grid(daily_map)

    def _render_calendar_grid(self, daily_map: dict):
        # Clear existing tiles
        while self.calendar_grid_layout.count():
            item = self.calendar_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Build current month matrix (Weeks x 7 days)
        cal = calendar.monthcalendar(self.current_year, self.current_month)
        now_d = self.today_date

        for row_idx, week in enumerate(cal):
            for col_idx, day_num in enumerate(week):
                if day_num == 0:
                    tile = CalendarDayTile(None, None)
                else:
                    date_str = f"{self.current_year:04d}-{self.current_month:02d}-{day_num:02d}"
                    day_data = daily_map.get(date_str, {})
                    is_today = (self.current_year == now_d.year and self.current_month == now_d.month and day_num == now_d.day)
                    tile = CalendarDayTile(day_num, day_data, is_today=is_today)

                self.calendar_grid_layout.addWidget(tile, row_idx, col_idx)


class StudentAttendanceHeatmapDialog(QDialog):
    """
    Modal Dialog to view any student's Current Month Attendance Heatmap from Directory.
    """
    def __init__(self, student: dict, parent=None):
        super().__init__(parent)
        self.student = student or {}
        self.setWindowTitle(f"Attendance Heatmap — {self.student.get('full_name', 'Student')}")
        self.setMinimumSize(920, 640)
        self.resize(960, 680)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog { background-color: #e8edf5; }")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Scroll Area for Heatmap & Analytics
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(14)

        # Student Details Banner
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background-color: #0f172a; border-radius: 12px; padding: 12px 18px;
            }
        """)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(12, 8, 12, 8)
        
        b_info = QVBoxLayout()
        b_name = QLabel(f"🎓 {self.student.get('full_name', 'Student Name')} ({self.student.get('registration_number', '-')})")
        b_name.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff; border: none; background: transparent;")
        
        b_course = QLabel(f"Course: {self.student.get('class_name', 'General')} | Email: {self.student.get('email', '-')}")
        b_course.setStyleSheet("font-size: 12px; color: #94a3b8; border: none; background: transparent;")
        
        b_info.addWidget(b_name)
        b_info.addWidget(b_course)
        b_layout.addLayout(b_info)
        b_layout.addStretch()

        c_layout.addWidget(banner)

        # Embed Analytics & Heatmap Widget
        analytics_widget = StudentAttendanceAnalyticsWidget(student_id=self.student.get("id"), user_info=self.student)
        c_layout.addWidget(analytics_widget)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Close Button
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        close_btn = QPushButton("Done / Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: #ffffff; font-weight: 700; font-size: 13px;
                padding: 8px 24px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)
