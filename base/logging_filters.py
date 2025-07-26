import logging
from django.core.exceptions import DisallowedHost


class DisallowedHostFilter(logging.Filter):
    """
    Check if a log record contains a DisallowedHost exception
    Lower log level to WARNING and remove traceback.
    """
    def filter(self, record) -> bool:
        exc = record.__dict__.get("exc_info")
        if exc:
            exc_type = exc[0]
            if exc_type is DisallowedHost:
                record.levelno = logging.WARNING
                record.levelname = "WARNING"
                record.exc_info = None
        return True
