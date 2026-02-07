import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import time_machine

from src.movies.utils.request_limiter import RequestLimiter


class TestRequestLimiter(unittest.TestCase):
    def setUp(self):
        self.max_requests = 10
        self.request_limiter = RequestLimiter(max_requests=self.max_requests)

    @patch("datetime.datetime")
    def test_can_make_request_within_limit(self, mock_datetime):
        fixed_time = datetime(2024, 6, 20, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time

        for _ in range(self.max_requests):
            self.assertTrue(self.request_limiter.can_make_request())

        self.assertFalse(self.request_limiter.can_make_request())

    def test_reset_after_day(self):
        with time_machine.travel(datetime(2024, 6, 20, 12, 0, 0)) as traveller:
            self.max_requests = 10
            self.request_limiter = RequestLimiter(max_requests=self.max_requests)
            for _ in range(self.max_requests):
                self.assertTrue(self.request_limiter.can_make_request())

            self.assertFalse(self.request_limiter.can_make_request())
            traveller.shift(timedelta(days=1, seconds=1))

            self.assertTrue(self.request_limiter.can_make_request())
            self.assertEqual(self.request_limiter.request_count, 1)
