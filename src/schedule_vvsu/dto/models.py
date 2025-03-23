from pydantic import BaseModel
from datetime import datetime, date, time
import pytz


class Lesson(BaseModel):
    date: str  # Например: "Вторник 11.02.2025" или "11.02.2025"
    time_range: str  # Например: "18:30-20:00"
    discipline: str
    lesson_type: str
    auditorium: str
    teacher: str

    def get_date(self) -> date:
        """
        Возвращает объект date, извлеченный из строки date.
        Если присутствует день недели, используется второй элемент.
        """
        parts = self.date.split(" ")
        date_str = parts[1] if len(parts) > 1 else parts[0]
        return datetime.strptime(date_str, "%d.%m.%Y").date()

    def get_start_end_times(self) -> tuple[time, time]:
        """
        Разбивает строку time_range и возвращает кортеж с объектами time: (start_time, end_time)
        """
        start_str, end_str = self.time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
        return start_time, end_time


class CalendarEvent(BaseModel):
    summary: str
    start: datetime
    end: datetime
    location: str
    description: str
    extended_properties: dict

    @classmethod
    def from_lesson(cls, lesson: Lesson, is_first_of_day: bool = False,
                    timezone_str: str = "Asia/Vladivostok") -> "CalendarEvent":
        """
        Преобразует объект Lesson в объект CalendarEvent.
        Добавляет в описание строку обновления с текущим временем в формате "MM.DD в HH:MM".
        """
        tz = pytz.timezone(timezone_str)
        lesson_date = lesson.get_date()  # Получаем дату из строки
        start_time, end_time = lesson.get_start_end_times()
        start_dt = tz.localize(datetime.combine(lesson_date, start_time))
        end_dt = tz.localize(datetime.combine(lesson_date, end_time))
        update_time = datetime.now(tz).strftime("%m.%d в %H:%M")
        description = f"Преподаватель: {lesson.teacher}\nUpdate: {update_time}"
        summary = f"{lesson.discipline} ({lesson.lesson_type})"
        lesson_key = f"{lesson.date}_{lesson.time_range}_{lesson.discipline}_{lesson.teacher}"
        return cls(
            summary=summary,
            start=start_dt,
            end=end_dt,
            location=lesson.auditorium,
            description=description,
            extended_properties={"lesson_key": lesson_key}
        )
