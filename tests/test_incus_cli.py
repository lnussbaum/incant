from incant.incus_cli import IncusCLI
from incant.reporter import Reporter


class TestIncusCLI:
    def test_contructor(self):
        reporter = Reporter()
        IncusCLI(reporter=reporter)
