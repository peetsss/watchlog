from datetime import datetime, timedelta
from threading import Lock


class RequestLimiter:
    def __init__(self, max_requests: int = 950):
        self.max_requests = max_requests
        self.request_count = 0
        self.last_reset = self.get_next_reset_time()
        self.lock = Lock()

    def get_next_reset_time(self) -> datetime:
        now = datetime.now()
        reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return reset_time

    def can_make_request(self) -> bool:
        current_time = datetime.now()

        with self.lock:
            if current_time > self.last_reset:
                self.request_count = 0
                self.last_reset = self.get_next_reset_time()

            if self.request_count < self.max_requests:
                self.request_count += 1
                return True
            else:
                return False


request_limiter = RequestLimiter(max_requests=950)
