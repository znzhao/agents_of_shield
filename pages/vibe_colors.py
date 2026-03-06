"""Vibe color mapping for consistent styling across all pages"""

VIBE_COLORS = {
    "tense": "#e74c3c",
    "emotional": "#e91e63",
    "action-packed": "#f39c12",
    "comedic": "#f1c40f",
    "mysterious": "#8e44ad",
    "romantic": "#e91e63",
    "tragic": "#34495e",
    "hopeful": "#27ae60",
    "suspenseful": "#c0392b",
    "dramatic": "#2980b9",
    "dark": "#1a252f",
    "lighthearted": "#f39c12",
    "intense": "#e74c3c",
    "melancholic": "#95a5a6",
    "thrilling": "#c0392b",
}


def get_vibe_color(vibe: str, default_color: str = "#5d6f7f") -> str:
    """
    Get the color for a vibe.
    
    Args:
        vibe: The vibe name (e.g., 'tense', 'emotional')
        default_color: Color to use if vibe is not found (default is theme primary_light)
    
    Returns:
        Hex color code for the vibe
    """
    return VIBE_COLORS.get(vibe, default_color)
