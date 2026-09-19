"""BakenOS compatibility policy for the legacy modular adapter.

This module is deliberately not imported by the public production package.
It only registers Baken-specific exceptions needed by the compatibility/kernel
integration path while the Baken adapter is being extracted from compiler core.
"""

_SAFE_SYSTEM_BUILTINS = (
    "baken_get_font_advances",
    "baken_get_font_alpha",
    "baken_get_font_width",
    "baken_get_font_height",
    "baken_get_font_px",
    "baken_get_cjk_width",
    "baken_get_cjk_height",
    "baken_get_cjk_alpha",
    "baken_get_logo_pixels",
    "baken_get_logo_size",
    "baken_srgb_to_linear",
    "baken_linear_to_srgb",
    "baken_get_app_icon_alpha",
    "baken_get_motion_icon_alpha",
)


def install(bootstrap) -> None:
    """Register Baken-only safe system builtins on an already installed frontend."""
    try:
        from . import language_safety
    except ImportError:
        import language_safety

    language_safety.register_safe_system_builtins(_SAFE_SYSTEM_BUILTINS)


__all__ = ["install"]
