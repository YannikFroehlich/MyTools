# MyTools UI Styleguide

This is the living reference for the visual language of MyTools. Read it before every repository task. For UI work, use it together with an existing, comparable page and keep it up to date whenever a reusable convention changes.

The application code remains the implementation source of truth. This document explains how to use that system consistently instead of replacing it.

## 1. Source files and CSS order

The central files are:

- `app/templates/app/base.html`: global page shell, header, theme editor and stylesheet order.
- `app/static/app/js/base.js`: theme presets, dark mode and display-option persistence.
- `app/static/app/css/core.css`: CSS bundle that is actually loaded globally; it contains the base layout, icons, profile menu and contrast rules.
- `app/static/app/css/base.css`, `icons/custom_icons.css`, `profile_menu.css`, `contrast.css`: source/reference files represented in the core bundle.
- `app/static/app/css/tool_pages.css`: shared visual layer for tool pages and reusable component groups.
- Feature CSS such as `calculator.css`, `weather.css` or `file_converter.css`: layout and behavior unique to one feature.

The order in `base.html` is important:

1. `core.css`
2. the page's `{% block extra_css %}`
3. `tool_pages.css`

`tool_pages.css` therefore intentionally normalizes many feature styles after the feature stylesheet. Prefer shared tokens and the selectors in `tool_pages.css` over increasingly specific overrides. Do not assume that editing `base.css` alone changes the running application: the browser loads `core.css`.

## 2. Visual character

MyTools uses a compact, card-based interface with:

- DM Sans as the global typeface;
- large rounded surfaces and smaller rounded controls;
- a two-color theme gradient for primary actions and important icons;
- lightly tinted theme surfaces instead of flat, hard-coded blue panels;
- soft borders and restrained colored shadows;
- left-aligned content; centered text is mainly for previews, empty states and drop zones;
- short hover movement, while all functionality remains understandable without animation;
- responsive layouts for desktop, tablet and mobile.

The selected theme must recolor the interface. Hard-coded brand blue is not a valid default for a new generic component. Fixed colors are reserved for semantic states such as success, warning and destructive actions, or for a feature with a deliberate identity.

## 3. Theme system

### 3.1 Body states

Theme behavior is expressed through body classes:

| Class | Meaning |
| --- | --- |
| `dark-mode` | Dark appearance selected by the user. |
| `custom-theme` | One of the selectable presets is active. |
| `theme-lunora-mode` | Lunora's complete visual treatment is active. |
| `theme-pattern-mode` | Decorative theme-colored page background is active. |
| `theme-high-contrast-mode` | Stronger borders, surfaces and text contrast are required. |
| `theme-reduced-motion-mode` | Animations and smooth scrolling are effectively disabled. |

The relevant local-storage keys are `theme`, `themePreset` and `customThemeDisplayOptions`. Theme state must be changed through the existing logic in `base.js`, not through a second feature-specific persistence system.

### 3.2 Global tokens

Use these variables in new generic UI:

| Token | Purpose |
| --- | --- |
| `--theme-page-bg` | Page background. |
| `--theme-text` | Default text on the page background. |
| `--theme-nav-start`, `--theme-nav-end` | Header gradient. |
| `--theme-accent-start`, `--theme-accent-end` | Primary gradient and accents. |
| `--theme-accent-text` | Readable text/icon color on the primary gradient. |
| `--theme-accent-rgb`, `--theme-accent-end-rgb` | RGB triplets for alpha colors and shadows. |
| `--theme-card-bg`, `--theme-card-text` | Preset-aware card surface and its readable text. Always provide a fallback. |
| `--theme-card-radius` | Preset-aware radius. Always provide a fallback. |
| `--theme-footer-bg`, `--theme-footer-text`, `--theme-footer-border` | Footer surface, text and divider. |
| `--theme-nav-shadow` | Header shadow color. |

Correct alpha usage:

```css
.example {
    border-color: rgba(var(--theme-accent-rgb), 0.22);
    box-shadow: 0 18px 46px rgba(var(--theme-accent-rgb), 0.10);
}
```

Do not put the hex token into `rgba()`. Use `rgba(var(--theme-accent-rgb), alpha)` or `color-mix()`.

### 3.3 Selectable presets

Each preset has separate light and dark values. The first pair is the accent gradient; the other values are page/card backgrounds.

| Preset | Light | Dark |
| --- | --- | --- |
| Sky | `#1a56d6` → `#5aadee`; `#dce5f5` / `#ffffff` | `#0e2d6e` → `#2a6ea0`; `#12151f` / `#1c2231` |
| Forest | `#0f766e` → `#34d399`; `#dff3ec` / `#f7fffb` | `#064e3b` → `#047857`; `#0f1f1b` / `#13231f` |
| Rose | `#be185d` → `#fb7185`; `#f8dfe8` / `#fff7fa` | `#831843` → `#be185d`; `#21121b` / `#2a1621` |
| Graphite | `#111827` → `#64748b`; `#e2e8f0` / `#f8fafc` | `#020617` → `#334155`; `#111827` / `#1f2937` |
| Violet | `#6d28d9` → `#a78bfa`; `#ede9fe` / `#faf5ff` | `#4c1d95` → `#7c3aed`; `#171026` / `#211734` |
| Sunset | `#ea580c` → `#facc15`; `#ffedd5` / `#fff7ed` | `#7c2d12` → `#c2410c`; `#1f130d` / `#2c1a10` |
| Lunora | `#9b6b38` → `#d6ad73`; `#f4f1e8` / `#fffaf4` | `#b78a55` → `#e7c894`; `#19100a` / `#251d16` |

The base theme and a selected Sky preset use the same main light colors, but are not identical states: selecting a preset also supplies card tokens and a `22px` card radius. Lunora supplies a `24px` card radius and additional structural styling.

### 3.4 Tool-page tokens

Pages covered by `tool_pages.css` derive a smaller component system from the global theme:

```css
.new-tool-page {
    --tool-card-bg: var(--theme-card-bg, rgba(255, 255, 255, 0.9));
    --tool-card-text: var(--theme-card-text, var(--theme-text));
    --tool-muted: color-mix(in srgb, var(--tool-card-text) 84%, transparent);
    --tool-line: rgba(var(--theme-accent-rgb), 0.22);
    --tool-line-strong: rgba(var(--theme-accent-end-rgb), 0.34);
    --tool-soft: rgba(var(--theme-accent-rgb), 0.10);
    --tool-surface: linear-gradient(
        135deg,
        rgba(var(--theme-accent-rgb), 0.10),
        rgba(var(--theme-accent-end-rgb), 0.08)
    ), var(--tool-card-bg);
    --tool-surface-strong: linear-gradient(
        135deg,
        rgba(var(--theme-accent-rgb), 0.14),
        rgba(var(--theme-accent-end-rgb), 0.10)
    ), var(--tool-card-bg);
    --tool-accent-readable: color-mix(
        in srgb,
        var(--theme-accent-start) 38%,
        var(--tool-card-text) 62%
    );
    --tool-input-bg: color-mix(
        in srgb,
        var(--tool-card-bg) 88%,
        var(--theme-accent-start) 12%
    );
    --tool-radius: var(--theme-card-radius, 28px);
    --tool-shadow: 0 22px 60px rgba(var(--theme-accent-rgb), 0.13);
    color: var(--tool-card-text);
}

body.dark-mode .new-tool-page {
    --tool-muted: color-mix(in srgb, var(--tool-card-text) 88%, transparent);
    --tool-accent-readable: color-mix(
        in srgb,
        var(--theme-accent-end) 28%,
        #ffffff 72%
    );
    --tool-input-bg: color-mix(in srgb, var(--tool-card-bg) 82%, #020617 18%);
    --tool-shadow: 0 22px 64px rgba(0, 0, 0, 0.28);
}
```

When adding a new main tool-page wrapper, add it to the appropriate `:where(...)` groups in `tool_pages.css`; otherwise it will not inherit the complete shared system.

## 4. Layout and spacing

Use the file-converter layout as the clearest general reference for a new tool page:

```css
.new-tool-page {
    width: min(1180px, calc(100% - 32px));
    margin: 34px auto 70px;
}

.new-tool-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(310px, 0.9fr);
    gap: 22px;
    margin-top: 22px;
    align-items: start;
}

@media (max-width: 880px) {
    .new-tool-layout {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 560px) {
    .new-tool-page {
        width: min(100% - 18px, 1180px);
        margin-top: 18px;
    }
}
```

Preferred spacing values are `8`, `10`, `12`, `14`, `16`, `18`, `22`, `24`, `28`, `34` and `38px`. Use `clamp()` for large responsive padding. Common structural breakpoints are `880px` for two-column layouts, `640/560px` for mobile components and `420px` for very compact navigation.

Use `minmax(0, 1fr)` for grid children that may contain long text. Interactive content must not rely on horizontal scrolling, except explicitly scrollable rows such as the compact header controls.

## 5. Typography

- Font: `'DM Sans', sans-serif`.
- Hero title: usually `clamp(2rem, 4vw, 3.5rem)`, tight line height around `1` to `1.1`.
- Section title: around `1.25rem` to `1.4rem`.
- Body copy: around `1rem`, line height `1.55` to `1.65`.
- Kicker/eyebrow: small uppercase text, `font-weight: 900`, `letter-spacing: 0.08em`.
- Muted copy uses `--tool-muted`; do not lower opacity until it becomes hard to read.
- Keep headings, labels, card copy and controls left-aligned unless the component is genuinely a centered preview or empty state.

Do not introduce a second global typeface for a feature. Only the weights `400`, `500` and `600` are currently requested from Google Fonts, even though some existing UI uses synthesized heavier weights.

## 6. Component recipes

### 6.1 Hero

A hero is a strong card, not a full-bleed banner. It uses the normal card text, a theme-tinted surface, the main radius and one decorative glow.

```css
.new-tool-hero {
    position: relative;
    overflow: hidden;
    padding: clamp(22px, 4vw, 38px);
    border: 1px solid var(--tool-line);
    border-radius: var(--tool-radius);
    background: var(--tool-surface-strong);
    color: var(--tool-card-text);
    box-shadow: var(--tool-shadow);
}

.new-tool-hero::after {
    content: "";
    position: absolute;
    right: -90px;
    bottom: -130px;
    width: 280px;
    height: 280px;
    border-radius: 999px;
    background: radial-gradient(
        circle,
        rgba(var(--theme-accent-end-rgb), 0.30),
        transparent 68%
    );
    pointer-events: none;
}
```

Content inside a hero with a pseudo-element must be positioned above it with `position: relative; z-index: 1`.

### 6.2 Card or box

```css
.new-tool-card {
    padding: clamp(18px, 3vw, 28px);
    border: 1px solid var(--tool-line);
    border-radius: var(--tool-radius);
    background: var(--tool-surface);
    color: var(--tool-card-text);
    box-shadow: 0 18px 46px rgba(var(--theme-accent-rgb), 0.10);
}
```

Nested boxes use `--tool-soft`, `--tool-line-strong` and a radius about `10px` smaller than the parent. Avoid stacking several equally strong shadows inside one card.

### 6.3 Primary button

```css
.new-tool-primary {
    min-height: 44px;
    padding: 0 18px;
    border: 0;
    border-radius: 18px;
    background: linear-gradient(
        135deg,
        var(--theme-accent-start),
        var(--theme-accent-end)
    );
    color: var(--theme-accent-text);
    font-weight: 900;
    box-shadow: 0 16px 34px rgba(var(--theme-accent-rgb), 0.24);
    cursor: pointer;
    transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
}

.new-tool-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 20px 42px rgba(var(--theme-accent-rgb), 0.30);
}
```

Use one visually dominant primary action per local section. Text and icons on the gradient always use `--theme-accent-text`, never a guessed white or dark color.

### 6.4 Secondary button, tab or chip

```css
.new-tool-secondary {
    min-height: 44px;
    padding: 0 16px;
    border: 1px solid rgba(var(--theme-accent-rgb), 0.24);
    border-radius: 16px;
    background: rgba(var(--theme-accent-rgb), 0.13);
    color: color-mix(
        in srgb,
        var(--theme-accent-start) 36%,
        var(--tool-card-text) 64%
    );
    font-weight: 900;
}
```

Active tabs use a stronger mixed gradient, a stronger end-accent border and `--tool-card-text`. A compact chip may be shorter than `44px`, but it must have a sufficiently large clickable wrapper.

### 6.5 Form field

```css
.new-tool-field {
    width: 100%;
    min-height: 46px;
    padding: 11px 14px;
    border: 1px solid var(--tool-line);
    border-radius: 16px;
    background: var(--tool-input-bg);
    color: var(--tool-card-text);
}

.new-tool-field:focus-visible {
    outline: none;
    border-color: rgba(var(--theme-accent-end-rgb), 0.72);
    box-shadow: 0 0 0 4px rgba(var(--theme-accent-rgb), 0.16);
}
```

Every field needs a visible label. Placeholder text is supplementary, not a replacement for a label. `select option` needs a readable explicit background in dark mode when browser defaults are insufficient.

### 6.6 Icon tile

Important feature icons use the accent gradient, `--theme-accent-text`, a rounded square and a colored shadow. Typical sizes are `42px` for compact lists and `64–76px` for heroes or drop zones. Do not place several competing large icon tiles in one card.

### 6.7 Status and destructive actions

Theme colors communicate selection and hierarchy. Semantic colors communicate meaning:

- success: green;
- warning: amber/orange;
- error or destructive action: red;
- informational/default action: the active theme accent.

A destructive button must remain recognizably red in every preset. Do not recolor delete actions with the active theme gradient. Combine color with an icon or clear label; never communicate status through color alone.

## 7. Interaction and accessibility

- Use semantic `<button>` and `<a>` elements. Add `type="button"` unless a button intentionally submits a form.
- Icon-only controls require an `aria-label` and usually a `title`.
- Toggle buttons require `aria-pressed`; expandable controls require `aria-expanded`.
- Keyboard focus must be at least as visible as hover. Use `:focus-visible` and a theme-colored ring.
- Hover movement is normally `translateY(-1px)` for buttons and at most `-2px` for cards.
- Typical transitions are `0.18s ease`; avoid long decorative motion for routine actions.
- Global pages keep their window scroll position per URL and browser tab through `base.js`; reload-style actions must not replace this with feature-specific scroll persistence. URL fragments keep the browser's native anchor behavior.
- Support both `body.theme-reduced-motion-mode` and `@media (prefers-reduced-motion: reduce)` for newly animated components.
- In high-contrast mode, use solid card backgrounds, clear text, `2px` borders where necessary and no meaning conveyed only by transparency.
- General touch targets should be at least `44 × 44px`. The compact header has established `38–40px` controls as a deliberate exception.
- User-facing template text must use Django `{% translate %}` / `{% blocktranslate %}`.

Recommended motion override:

```css
body.theme-reduced-motion-mode .new-component,
body.theme-reduced-motion-mode .new-component::before,
body.theme-reduced-motion-mode .new-component::after {
    animation: none !important;
    transition: none !important;
}

@media (prefers-reduced-motion: reduce) {
    .new-component,
    .new-component::before,
    .new-component::after {
        animation: none !important;
        transition: none !important;
    }
}
```

## 8. Lunora

Lunora is a complete theme, not just another accent pair. It adds warm parchment-like backgrounds, warm ink and borders, a floating rounded header, softer pill-shaped controls and its own light/dark panel values.

Generic components should work in Lunora automatically through the global and tool tokens. Only add a Lunora-specific rule when the component cannot be expressed through those tokens:

```css
body.theme-lunora-mode .new-tool-card {
    border-color: var(--lunora-theme-border);
    background: var(--lunora-theme-panel);
    color: var(--lunora-theme-ink);
    box-shadow: 0 18px 46px var(--lunora-theme-shadow);
}

body.dark-mode.theme-lunora-mode .new-tool-card {
    background: var(--lunora-theme-panel-strong);
}
```

Never use `--lunora-*` variables outside a `theme-lunora-mode` selector because they do not exist in the other presets.

## 9. Definition of done for visible changes

Before considering a UI change complete, verify:

- the template extends `app/base.html` unless it is an intentional standalone shell;
- generic colors come from theme or tool tokens rather than fixed blue values;
- cards, buttons, fields, icons and text hierarchy match the recipes above or an existing comparable component;
- the result works without a selected preset, in light and dark mode;
- at least one non-blue preset and Lunora were checked;
- background effect does not reduce readability;
- high contrast keeps borders, focus and text clear;
- reduced motion removes newly added animation;
- keyboard focus, labels and ARIA state are present;
- layouts work around `880px`, `640/560px` and narrow mobile widths;
- long translated text can wrap without clipping;
- relevant Django tests and the appropriate verification command pass;
- this guide is updated if the work created or changed a reusable convention.
