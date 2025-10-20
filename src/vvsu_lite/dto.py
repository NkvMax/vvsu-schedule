
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Lesson:
    date: str
    time_range: str
    discipline: str
    lesson_type: str
    auditorium: str
    teacher: str
    webinar_url: Optional[str] = None
