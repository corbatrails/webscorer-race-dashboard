import json
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
THEME_CSS = REPO_ROOT / "static" / "theme.css"
TV_CSS = REPO_ROOT / "static" / "style.css"
VENDOR_DIR = REPO_ROOT / "static" / "vendor"


def contrast_ratio(foreground: str, background: str) -> float:
    def relative_luminance(color: str) -> float:
        channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def composite_rgba(foreground: str, background: str) -> str:
    match = re.fullmatch(
        r"rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*(0(?:\.\d+)?|1(?:\.0+)?)\s*\)",
        foreground,
    )
    assert match, f"invalid rgba color: {foreground}"
    red, green, blue = (int(value) for value in match.groups()[:3])
    alpha = float(match.group(4))
    background_channels = [
        int(background[index:index + 2], 16)
        for index in (1, 3, 5)
    ]
    composited = [
        round(channel * alpha + background_channel * (1 - alpha))
        for channel, background_channel in zip(
            (red, green, blue),
            background_channels,
        )
    ]
    return "#" + "".join(f"{channel:02X}" for channel in composited)


def _tokens(theme: str) -> dict[str, str]:
    css = THEME_CSS.read_text(encoding="utf-8")
    match = re.search(
        rf'\[data-theme="{theme}"\]\s*\{{(?P<body>.*?)\}}',
        css,
        flags=re.DOTALL,
    )
    assert match, f"missing {theme} theme block"
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})", match.group("body")))


def _raw_tokens(theme: str) -> dict[str, str]:
    css = THEME_CSS.read_text(encoding="utf-8")
    match = re.search(
        rf'\[data-theme="{theme}"\]\s*\{{(?P<body>.*?)\}}',
        css,
        flags=re.DOTALL,
    )
    assert match, f"missing {theme} theme block"
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", match.group("body")))


@pytest.mark.parametrize(
    ("foreground", "background"),
    [
        ("--text-primary", "--bg-primary"),
        ("--text-primary", "--bg-card"),
        ("--text-body", "--bg-primary"),
        ("--text-body", "--bg-card"),
        ("--text-muted", "--bg-primary"),
        ("--text-muted", "--bg-card"),
        ("--text-dim", "--bg-primary"),
        ("--accent-primary", "--bg-primary"),
        ("--accent-secondary", "--bg-primary"),
        ("--error-color", "--bg-primary"),
        ("--success-color", "--bg-primary"),
    ],
)
def test_light_meaningful_text_has_enhanced_contrast(foreground, background):
    tokens = _tokens("light")
    assert contrast_ratio(tokens[foreground], tokens[background]) >= 7


@pytest.mark.parametrize(
    ("foreground", "background"),
    [
        ("--border-color", "--bg-primary"),
        ("--accent-primary", "--bg-track"),
    ],
)
def test_light_dividers_and_progress_fill_are_distinguishable(foreground, background):
    tokens = _tokens("light")
    assert contrast_ratio(tokens[foreground], tokens[background]) >= 3


@pytest.mark.parametrize(
    ("foreground", "background"),
    [
        ("--text-primary", "--bg-primary"),
        ("--text-primary", "--bg-card"),
        ("--text-body", "--bg-primary"),
        ("--text-body", "--bg-card"),
        ("--text-muted", "--bg-primary"),
        ("--text-muted", "--bg-card"),
        ("--text-dim", "--bg-primary"),
        ("--accent-primary", "--bg-primary"),
        ("--accent-secondary", "--bg-primary"),
        ("--error-color", "--bg-primary"),
        ("--success-color", "--bg-primary"),
    ],
)
def test_dark_meaningful_text_has_wcag_aa_contrast(foreground, background):
    tokens = _tokens("dark")
    assert contrast_ratio(tokens[foreground], tokens[background]) >= 4.5


@pytest.mark.parametrize(
    ("foreground", "background"),
    [
        ("--border-color", "--bg-card"),
        ("--accent-primary", "--bg-track"),
    ],
)
def test_dark_boundaries_and_progress_fill_are_distinguishable(foreground, background):
    tokens = _tokens("dark")
    assert contrast_ratio(tokens[foreground], tokens[background]) >= 3


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_bootstrap_outline_buttons_use_theme_colors_and_states(theme):
    css = THEME_CSS.read_text(encoding="utf-8")
    tokens = _tokens(theme)
    rules = {}
    for selector in (".btn-outline-primary", ".btn-outline-secondary"):
        match = re.search(
            rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]+)\}}",
            css,
        )
        assert match, f"{selector} needs explicit Woodland button colors"
        rules[selector] = dict(
            re.findall(r"(--[\w-]+):\s*([^;]+);", match.group("body"))
        )

    primary = rules[".btn-outline-primary"]
    assert primary["--bs-btn-color"] == "var(--accent-primary)"
    assert primary["--bs-btn-hover-color"] == "var(--bg-primary)"
    assert primary["--bs-btn-hover-bg"] == "var(--accent-primary)"
    assert primary["--bs-btn-active-color"] == "var(--bg-primary)"
    assert primary["--bs-btn-focus-shadow-rgb"] == "var(--bs-primary-rgb)"

    secondary = rules[".btn-outline-secondary"]
    assert secondary["--bs-btn-color"] == "var(--text-muted)"
    assert secondary["--bs-btn-hover-color"] == "var(--text-primary)"
    assert secondary["--bs-btn-hover-bg"] == "var(--bg-track)"
    assert secondary["--bs-btn-focus-shadow-rgb"] == "var(--bs-secondary-color-rgb)"

    for surface in ("--bg-primary", "--bg-card"):
        assert contrast_ratio(tokens["--accent-primary"], tokens[surface]) >= 4.5
        assert contrast_ratio(tokens["--text-muted"], tokens[surface]) >= 4.5
    assert contrast_ratio(tokens["--bg-primary"], tokens["--accent-primary"]) >= 4.5
    assert contrast_ratio(tokens["--text-primary"], tokens["--bg-track"]) >= 4.5


def test_race_control_name_cells_reserve_space_for_split_buttons():
    css = (REPO_ROOT / "static" / "race_control.css").read_text(encoding="utf-8")
    match = re.search(r"#control-table\s+\.col-name\s*\{(?P<body>[^}]+)\}", css)
    assert match, "name-cell padding must override Bootstrap table cell padding"
    declarations = dict(
        re.findall(r"([\w-]+):\s*([^;]+);", match.group("body"))
    )
    assert declarations["padding-right"] == "42px"


def test_summary_progress_count_uses_a_contrast_safe_surface():
    css = (REPO_ROOT / "static" / "style.css").read_text(encoding="utf-8")
    match = re.search(r"\.progress-bar-count\s*\{(?P<body>[^}]+)\}", css)
    assert match, "summary progress count needs a dedicated readable label surface"
    declarations = dict(
        re.findall(r"([\w-]+):\s*([^;]+);", match.group("body"))
    )
    assert declarations["color"] == "var(--text-primary)"
    assert declarations["background"] == "var(--bg-card)"
    assert declarations["left"] == "50%"
    assert declarations["transform"] == "translateX(-50%)"
    assert declarations["width"] == "fit-content"


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("surface", ["--bg-card", "--bg-primary"])
def test_bootstrap_card_border_is_distinguishable_on_theme_surfaces(theme, surface):
    tokens = _tokens(theme)
    raw_tokens = _raw_tokens(theme)
    rendered_border = composite_rgba(
        raw_tokens["--bs-border-color-translucent"],
        tokens[surface],
    )
    assert contrast_ratio(rendered_border, tokens[surface]) >= 3


def test_bootstrap_is_vendored_with_version_and_license_metadata():
    metadata = json.loads((VENDOR_DIR / "vendor.json").read_text(encoding="utf-8"))
    bootstrap = metadata["bootstrap"]
    assert bootstrap == {
        "version": "5.3.8",
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css",
        "file": "bootstrap.min.css",
        "license": "MIT",
    }

    css = (VENDOR_DIR / bootstrap["file"]).read_text(encoding="utf-8")
    assert re.search(r"Bootstrap\s+v5\.3\.8", css)
    assert "Licensed under MIT" in css


def test_tv_styles_preserve_fixed_viewport_layout_without_bootstrap_collisions():
    css = TV_CSS.read_text(encoding="utf-8")
    assert re.search(r"body\s*\{[^}]*overflow:\s*hidden;[^}]*height:\s*100vh;", css, re.DOTALL)
    assert re.search(r"\.page\s*\{[^}]*height:\s*100vh;", css, re.DOTALL)
    assert re.search(
        r"\.demographics-grid\s*\{[^}]*grid-template-columns:\s*1fr 1fr;"
        r"[^}]*grid-template-rows:\s*1fr 1fr;",
        css,
        re.DOTALL,
    )
    assert re.search(r"\.results-table\s*\{[^}]*table-layout:\s*fixed;", css, re.DOTALL)
    assert ".tv-toast" in css
    assert ".pause-indicator.is-visible" in css
    assert not re.search(r"(?m)^\s*\.toast(?:[.:\s,{])", css)
    assert not re.search(r"(?m)^\s*\.pause-indicator\.visible(?:[.:\s,{])", css)
