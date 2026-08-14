from locuslab import __version__
from locuslab.models import DocumentKind, FindingSeverity


def test_package_imports() -> None:
    assert __version__ == "0.1.0"
    assert DocumentKind.CER.value == "CER"
    assert FindingSeverity.MAJOR.value == "Major"
