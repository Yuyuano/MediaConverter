"""Material Design 3 Theme Manager — dual-theme token system with QSS rendering."""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger('MediaConverter')

# ── MD3 Dark Theme Tokens (seed #6750A4 Purple) ──

DARK_TOKENS: Dict[str, str] = {
    'surface':                      '#141218',
    'surface_container_lowest':     '#0F0D13',
    'surface_container_low':        '#1D1B20',
    'surface_container':            '#211F26',
    'surface_container_high':       '#2B2930',
    'surface_container_highest':    '#36343B',
    'surface_dim':                  '#141218',
    'on_surface':                   '#E6E1E5',
    'on_surface_variant':           '#CAC4D0',
    'on_surface_variant_dim':       '#CAC4D0',
    'on_surface_dim':               '#938F99',
    'outline':                      '#938F99',
    'outline_variant':              '#49454F',
    'outline_variant_dim':          '#36343B',
    'primary':                      '#D0BCFF',
    'on_primary':                   '#381E72',
    'primary_container':            '#4F378B',
    'on_primary_container':         '#EADDFF',
    'primary_fixed_dim':            '#B79BFF',
    'secondary':                    '#CCC2DC',
    'secondary_container':          '#4A4458',
    'on_secondary_container':       '#E8DEF8',
    'tertiary':                     '#EFB8C8',
    'tertiary_container':           '#633B48',
    'on_tertiary_container':        '#FFD8E4',
    'error':                        '#F2B8B5',
    'on_error':                     '#601410',
    'error_container':              '#8C1D18',
    'on_error_container':           '#F9DEDC',
    'success':                      '#A8E6CF',
    'warning':                      '#FFE082',
    'shadow':                       '0,0,0',
    'scrim':                        '0,0,0',
    'card_bg_alpha':                '0.82',
    'card_border_alpha':            '0.07',
    'btn_bg_alpha':                 '0.55',
    'btn_hover_alpha':              '0.65',
    'btn_pressed_alpha':            '0.50',
    'input_bg_alpha':               '0.55',
    'input_focus_alpha':            '0.70',
    'group_bg_alpha':               '0.40',
    'log_bg_alpha':                 '0.85',
    'sidebar_bg_alpha':             '0.90',
    'dialog_bg_alpha':              '0.97',
    'statusbar_bg_alpha':           '0.90',
}


def _hex_to_rgb(hex_color: str) -> tuple:
    """#RRGGBB or #RGB → (r, g, b)."""
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _blend(fg_hex: str, bg_hex: str, alpha: float) -> str:
    """Blend fg over bg at given alpha → solid #RRGGBB (MD3 state layer)."""
    fr, fg, fb = _hex_to_rgb(fg_hex)
    br, bg, bb = _hex_to_rgb(bg_hex)
    r = round(fr * alpha + br * (1 - alpha))
    g = round(fg * alpha + bg * (1 - alpha))
    b = round(fb * alpha + bb * (1 - alpha))
    return f"#{r:02X}{g:02X}{b:02X}"


def _derive_tokens(base: Dict[str, str]) -> Dict[str, str]:
    """Pre-compute solid derived tokens: container fills + pre-blended state layers.

    QSS cannot composite multiple background layers, so MD3 state layers
    (hover = content color @8%, pressed = @12%) are pre-blended into solid
    hex colors here. All derived tokens are opaque — no rgba translucency.
    """
    blend = lambda fg, bg, a: _blend(base[fg], base[bg], a)
    sc = lambda k: base[k]

    return {
        # Dividers / hairlines
        'divider':               sc('outline_variant'),
        'divider_subtle':        blend('outline_variant', 'surface_container_low', 0.5),
        # Card
        'card_bg':               sc('surface_container_low'),
        'card_border':           sc('outline_variant'),
        # Button (neutral filled)
        'btn_bg':                sc('surface_container_high'),
        'btn_hover':             blend('on_surface', 'surface_container_high', 0.08),
        'btn_pressed':           blend('on_surface', 'surface_container_high', 0.12),
        'btn_disabled_bg':       blend('on_surface', 'surface_container_low', 0.12),
        'btn_disabled_text':     blend('on_surface', 'surface_container_low', 0.38),
        # Primary filled button state layers (MD3: on-primary overlay @8%/12%)
        'primary_hover':         blend('on_primary', 'primary', 0.08),
        'primary_pressed':       blend('on_primary', 'primary', 0.12),
        # Chip (MD3 filter chip: outlined → secondary_container when checked)
        'chip_bg':               sc('surface_container_low'),
        'chip_border':           sc('outline_variant'),
        'chip_hover':            blend('on_surface', 'surface_container_low', 0.08),
        'chip_checked_bg':       sc('secondary_container'),
        'chip_checked_hover':    blend('on_secondary_container', 'secondary_container', 0.08),
        # Preset (small tonal button, same checked language as chip)
        'preset_bg':             sc('surface_container_high'),
        'preset_hover':          blend('on_surface', 'surface_container_high', 0.08),
        'preset_checked_bg':     sc('secondary_container'),
        'preset_checked_hover':  blend('on_secondary_container', 'secondary_container', 0.08),
        # Input (MD3 filled text field)
        'input_bg':              sc('surface_container_highest'),
        'input_hover_bg':        blend('on_surface', 'surface_container_highest', 0.08),
        'input_disabled_bg':     blend('on_surface', 'surface_container_low', 0.04),
        'input_disabled_text':   blend('on_surface', 'surface_container_low', 0.38),
        # Log
        'log_bg':                sc('surface_container_lowest'),
        # Popup / dialog (MD3 dialogs use surface_container_high)
        'popup_bg':              sc('surface_container_high'),
        'dialog_bg':             sc('surface_container_high'),
        # Table
        'table_bg':              sc('surface_container_low'),
        'table_header_bg':       sc('surface_container'),
        'table_gridline':        blend('outline_variant', 'surface_container_low', 0.5),
        'table_selected':        blend('primary', 'surface_container_low', 0.24),
        # List
        'list_bg':               sc('surface_container_low'),
        'list_hover':            blend('on_surface', 'surface_container_low', 0.08),
        'list_selected':         blend('primary', 'surface_container_low', 0.24),
        # Slider
        'slider_track':          sc('surface_container_highest'),
        'slider_track_disabled': blend('on_surface', 'surface_container_low', 0.12),
        'slider_handle_hover':   blend('on_primary', 'primary', 0.08),
        # Progress
        'progress_track':        sc('surface_container_highest'),
        # Sidebar (MD3 navigation drawer)
        'sidebar_bg':            sc('surface_container_low'),
        'sidebar_btn_hover':     blend('on_surface', 'surface_container_low', 0.08),
        'sidebar_btn_active':    sc('secondary_container'),
        'sidebar_btn_active_hover': blend('on_secondary_container', 'secondary_container', 0.08),
        # StatusBar
        'statusbar_bg':          sc('surface_container_low'),
        # Scrollbar
        'scrollbar_handle':      blend('on_surface_variant', 'surface', 0.35),
        'scrollbar_handle_hover': blend('on_surface_variant', 'surface', 0.55),
        # Section toggle
        'section_toggle_hover':  blend('on_surface', 'surface_container_low', 0.08),
        # Drop zone states (driven by dynamic "state" property in QSS)
        'drop_drag_bg':          blend('primary', 'surface_container_low', 0.10),
        'drop_selected_bg':      blend('primary', 'surface_container_low', 0.05),
        'drop_selected_border':  sc('outline'),
        # Type icon badge (file drop widget)
        'type_icon_bg':          blend('primary', 'surface_container_low', 0.14),
    }



# ── MD3 Light Theme Tokens ──

LIGHT_TOKENS: Dict[str, str] = {
    'surface':                      '#FFFBFE',
    'surface_container_lowest':     '#FFFFFF',
    'surface_container_low':        '#F7F2FA',
    'surface_container':            '#F3EDF7',
    'surface_container_high':       '#ECE6F0',
    'surface_container_highest':    '#E6E0E9',
    'surface_dim':                  '#DED8E1',
    'on_surface':                   '#1C1B1F',
    'on_surface_variant':           '#49454F',
    'on_surface_variant_dim':       '#49454F',
    'on_surface_dim':               '#49454F',
    'outline':                      '#79747E',
    'outline_variant':              '#CAC4D0',
    'outline_variant_dim':          '#CAC4D0',
    'primary':                      '#6750A4',
    'on_primary':                   '#FFFFFF',
    'primary_container':            '#EADDFF',
    'on_primary_container':         '#21005D',
    'primary_fixed_dim':            '#D0BCFF',
    'secondary':                    '#625B71',
    'secondary_container':          '#E8DEF8',
    'on_secondary_container':       '#1D192B',
    'tertiary':                     '#7D5260',
    'tertiary_container':           '#FFD8E4',
    'on_tertiary_container':        '#31111D',
    'error':                        '#B3261E',
    'on_error':                     '#FFFFFF',
    'error_container':              '#F9DEDC',
    'on_error_container':           '#410E0B',
    'success':                      '#3B7D5E',
    'warning':                      '#8C6D00',
    'shadow':                       '0,0,0',
    'scrim':                        '0,0,0',
    'card_bg_alpha':                '0.95',
    'card_border_alpha':            '0.12',
    'btn_bg_alpha':                 '0.10',
    'btn_hover_alpha':              '0.16',
    'btn_pressed_alpha':            '0.20',
    'input_bg_alpha':               '0.90',
    'input_focus_alpha':            '1.0',
    'group_bg_alpha':               '0.80',
    'log_bg_alpha':                 '0.95',
    'sidebar_bg_alpha':             '0.95',
    'dialog_bg_alpha':              '0.98',
    'statusbar_bg_alpha':           '0.92',
}

# Apply derived tokens
DARK_TOKENS.update(_derive_tokens(DARK_TOKENS))
LIGHT_TOKENS.update(_derive_tokens(LIGHT_TOKENS))


LOG_COLORS = {'info': '#89b4fa', 'error': '#f38ba8', 'warning': '#f9e2af'}
LOG_DOT = {'info': '●', 'error': '●', 'warning': '●'}
LOG_COLORS_MD3 = {'info': '#D0BCFF', 'error': '#F2B8B5', 'warning': '#FFE082'}
LOG_COLORS_MD3_LIGHT = {'info': '#6750A4', 'error': '#B3261E', 'warning': '#8C6D00'}


class ThemeManager:
    """MD3 dual-theme manager — hot-swap, QSS rendering, preference persistence."""

    THEMES = {'dark': DARK_TOKENS, 'light': LIGHT_TOKENS}
    _LOG_COLORS = {'dark': LOG_COLORS_MD3, 'light': LOG_COLORS_MD3_LIGHT}

    def __init__(self, app, root: Path):
        self._app = app
        self._root = root
        self._template_path = root / "gui" / "styles" / "material.qss"
        self._pref_path = root / "history" / ".theme_pref"
        self._current = self._load_pref()
        self._template = ""
        if self._template_path.exists():
            self._template = self._template_path.read_text(encoding='utf-8')

    @property
    def current(self) -> str:
        return self._current

    @property
    def tokens(self) -> Dict[str, str]:
        return self.THEMES[self._current]

    @property
    def log_colors(self) -> Dict[str, str]:
        return self._LOG_COLORS[self._current]

    def load_theme(self, name: str):
        if name not in self.THEMES:
            logger.warning(f"Unknown theme: {name}")
            return
        self._current = name
        if self._template:
            qss = self._template.format(**self.tokens)
            self._app.setStyleSheet(qss)
        self._save_pref()

    def toggle(self):
        self.load_theme('light' if self._current == 'dark' else 'dark')

    def color(self, key: str) -> str:
        return self.tokens.get(key, '#000000')

    def rgba(self, color_key: str, alpha_key: str) -> str:
        """Build rgba(r,g,b,alpha) from hex color + alpha float token."""
        hex_color = self.tokens.get(color_key, '#FFFFFF')
        alpha = float(self.tokens.get(alpha_key, '1.0'))
        r, g, b = _hex_to_rgb(hex_color)
        return f"rgba({r},{g},{b},{alpha:.2f})"

    def _load_pref(self) -> str:
        try:
            if self._pref_path.exists():
                data = json.loads(self._pref_path.read_text(encoding='utf-8'))
                name = data.get('theme', 'dark')
                if name in self.THEMES:
                    return name
        except (json.JSONDecodeError, OSError, TypeError, AttributeError):
            pass
        return 'dark'

    def _save_pref(self):
        try:
            self._pref_path.parent.mkdir(parents=True, exist_ok=True)
            self._pref_path.write_text(
                json.dumps({'theme': self._current}), encoding='utf-8'
            )
        except OSError as e:
            logger.debug(f"Failed to save theme pref: {e}")


def format_log_html(level: str, message: str) -> str:
    import html
    tm = get_theme()
    if tm is not None:
        colors = tm.log_colors
        color = colors.get(level, tm.tokens.get('on_surface_variant', '#a6adc8'))
    else:
        color = LOG_COLORS.get(level, '#a6adc8')
    dot = LOG_DOT.get(level, '○')
    escaped_msg = html.escape(message)
    return f'<span style="color:{color}">{dot}</span> {escaped_msg}'


def format_log_html_md3(level: str, message: str, theme_manager: ThemeManager) -> str:
    import html
    colors = theme_manager.log_colors
    color = colors.get(level, theme_manager.tokens.get('on_surface_variant', '#a6adc8'))
    dot = LOG_DOT.get(level, '○')
    escaped_msg = html.escape(message)
    return f'<span style="color:{color}">{dot}</span> {escaped_msg}'


# singleton — set by main.py after ThemeManager created
_theme_manager: Optional[ThemeManager] = None


def get_theme() -> Optional[ThemeManager]:
    return _theme_manager


def set_theme(tm: ThemeManager):
    global _theme_manager
    _theme_manager = tm
