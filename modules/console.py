from rich.console import Console
from rich.style import Style

# Universal Console Instance
console = Console()

# Professional Color Palette (Hex)
C_PRIMARY = "#00D7FF"    # Bright cyan
C_SECONDARY = "#AF87FF"  # Soft purple
C_SUCCESS = "#5FD75F"   # Muted green
C_WARNING = "#FFD700"   # Amber gold
C_ERROR = "#FF5F5F"     # Soft red
C_TEXT_PRI = "#FFFFFF"  # Pure white
C_TEXT_SEC = "#8A8A8A"  # Dim white
C_BORDER = "#3A3A3A"    # Dark slate

# Styles
S_HEADER = Style(color=C_PRIMARY, bold=True)
S_SUBTITLE = Style(color=C_TEXT_SEC)
S_BORDER = Style(color=C_BORDER)
S_TABLE_HEADER = Style(color=C_SECONDARY, bold=True)
S_RATING = Style(color=C_WARNING)
S_QUALITY = Style(color=C_PRIMARY)
S_SIZE_SEED = Style(color=C_SUCCESS)
