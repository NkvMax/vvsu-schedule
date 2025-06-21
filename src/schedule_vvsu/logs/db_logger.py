import logging
from schedule_vvsu.database import SessionLocal
from schedule_vvsu.db.models import LogEntry


class DBLogHandler(logging.Handler):
    def emit(self, record):
        session = SessionLocal()
        try:
            entry = LogEntry(level=record.levelname, message=self.format(record))
            session.add(entry)
            session.commit()
        except Exception as e:
            session.rollback()
            print("DBLogHandler error:", e)
        finally:
            session.close()
