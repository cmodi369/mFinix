from unittest import TestCase

from mFinix.webapp.mfinix_dashboard import Mfinix


class TestCache(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.webapp = Mfinix()
