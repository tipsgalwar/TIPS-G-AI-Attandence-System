from abc import ABC, abstractmethod
from datetime import datetime

class BasePlugin(ABC):
    """Abstract base class representing a plugin hook for Student Guardian AI extension module."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    def on_attendance_marked(self, student_id: int, status: str, check_in_time: datetime):
        """Called when a student check-in is logged."""
        pass

    def on_leave_submitted(self, leave_id: int, applicant_type: str, start_date: str):
        """Called when a leave request is submitted."""
        pass

    def on_holiday_created(self, holiday_id: int, holiday_name: str, date_str: str):
        """Called when a new holiday is added to the system."""
        pass
