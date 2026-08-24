import os
import unittest
from app.assistant_session import RohaSession
from app.config import OWNER_PIN


class TestCreatorAuth(unittest.TestCase):
    def setUp(self):
        self.db_path = "data/test_auth.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_authentication_and_locking(self):
        session = RohaSession()
        
        # Test locking session
        session.lock_session()
        self.assertFalse(session.is_verified)

        # Test invalid PIN
        self.assertFalse(session.authenticate("wrong_pin"))
        self.assertFalse(session.is_verified)

        # Test correct PIN
        self.assertTrue(session.authenticate(OWNER_PIN))
        self.assertTrue(session.is_verified)


if __name__ == "__main__":
    unittest.main()
