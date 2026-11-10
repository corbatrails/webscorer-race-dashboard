import json
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
THEME_CSS = REPO_ROOT / "static" / "theme.css"
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
