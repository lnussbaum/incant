from incant.incus_cli import IncusCLI
from incant.reporter import Reporter


class TestIncusCLI:
    def test_constructor(self):
        reporter = Reporter()
        IncusCLI(reporter=reporter)
