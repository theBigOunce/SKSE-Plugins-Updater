"""MO2 tool entry point; core imports work without MO2 or Qt."""

__version__ = "0.3.0"


def createPlugin():
    from .plugin import ScannerPlugin
    return ScannerPlugin()
