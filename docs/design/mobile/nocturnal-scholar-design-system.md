---
name: Nocturnal Scholar
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#393939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#c3c6d1'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#8d919b'
  outline-variant: '#424750'
  surface-tint: '#a8c8ff'
  primary: '#b5cfff'
  on-primary: '#003061'
  primary-container: '#8ab4f8'
  on-primary-container: '#0d4582'
  inverse-primary: '#315f9d'
  secondary: '#dfb7ff'
  on-secondary: '#4a067b'
  secondary-container: '#622893'
  on-secondary-container: '#d3a0ff'
  tertiary: '#65e1d8'
  on-tertiary: '#003734'
  tertiary-container: '#44c5bc'
  on-tertiary-container: '#004e4a'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d5e3ff'
  primary-fixed-dim: '#a8c8ff'
  on-primary-fixed: '#001b3c'
  on-primary-fixed-variant: '#114784'
  secondary-fixed: '#f1daff'
  secondary-fixed-dim: '#dfb7ff'
  on-secondary-fixed: '#2d004f'
  on-secondary-fixed-variant: '#622893'
  tertiary-fixed: '#7cf6ec'
  tertiary-fixed-dim: '#5dd9d0'
  on-tertiary-fixed: '#00201e'
  on-tertiary-fixed-variant: '#00504c'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  display-lg:
    fontFamily: Source Serif 4
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Source Serif 4
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Source Serif 4
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-sm:
    fontFamily: Source Serif 4
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1200px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style
The brand personality is intellectual, authoritative, and focused. This design system is tailored for academic research, high-density data analysis, and professional publishing environments where long-form reading and deep focus are required.

The design style is **Corporate Modern with Minimalist influences**, adapted for a high-performance dark environment. It prioritizes clarity and reduced eye strain through a sophisticated dark-on-dark layering system. The aesthetic response should be one of "quiet prestige"—feeling like a modern digital library or a high-end research laboratory at night.

## Colors
The palette is rooted in a deep charcoal base (`#121212`) to eliminate screen glare. Depth is achieved through a "lighter-is-higher" surface logic rather than traditional drop shadows.

- **Primary (Muted Blue):** Used for primary actions, links, and active states. It provides high legibility against dark backgrounds without being overstimulating.
- **Secondary (Soft Purple):** Used for accenting specific data types, citations, or highlights.
- **Tertiary (Teal):** Reserved for success states or specialized technical data visualizations.
- **Neutral Hierarchy:** Content is strictly tiered. Pure white is reserved for high-level headings, while light greys handle body text and metadata to maintain comfort during extended reading sessions.

## Typography
The typographic system utilizes a "Serif-for-Structure, Sans-for-System" approach.

- **Headlines:** Source Serif 4 provides a classic, authoritative feel that grounds the digital experience in academic tradition.
- **Body:** Inter is used for its exceptional legibility on digital displays, particularly in dark mode where "halation" (the glow of light text on dark) can occur.
- **Labels & Data:** JetBrains Mono is employed for metadata, citations, and technical labels to provide a precise, organized character that distinguishes system information from editorial content.

## Layout & Spacing
The design system uses a **Fixed Grid** philosophy for editorial content to ensure optimal line lengths for readability, while utilizing **Fluid containers** for dashboard-style interfaces.

- **Grid:** A 12-column grid on desktop with generous 24px gutters.
- **Rhythm:** An 8px linear scale governs all padding and margins. 
- **Adaptation:** 
  - **Desktop:** Wide margins (48px+) to create an "airy" feel despite the dark palette.
  - **Tablet:** Margins reduce to 32px; sidebars collapse into drawers.
  - **Mobile:** A 4-column layout with 16px margins. Typography scales down slightly to preserve vertical space.

## Elevation & Depth
In this dark mode system, depth is communicated through **Tonal Layers** and **Low-contrast Outlines** rather than heavy shadows.

- **Tiers:** The background is the lowest level (`#121212`). Surfaces that sit "above" it use incrementally lighter hex codes. 
- **Outlines:** To maintain crispness, all cards and floating elements use a subtle 1px border (`rgba(255, 255, 255, 0.1)`).
- **Shadows:** When necessary for high-elevation components (like Modals), use a large, soft 0% offset shadow with 40% opacity in pure black to "lift" the element without adding color noise.

## Shapes
The shape language is **Soft (0.25rem)**. This subtle rounding maintains the professional and academic rigor of the system while preventing it from feeling overly aggressive or "brutalist." 

- **Small Components:** Checkboxes and small tags use the base `rounded-sm`.
- **Large Components:** Cards and main content containers use `rounded-lg` (0.5rem) to provide a clear frame for the content.
- **Interaction States:** Hover states should not change the shape, only the background tone or border intensity.

## Components
- **Buttons:** Primary buttons use a solid Primary Blue with dark text for high contrast. Secondary buttons use a ghost style with the Primary Blue outline.
- **Inputs:** Fields use the `surface_low` background with a subtle bottom border. On focus, the border transitions to Primary Blue.
- **Cards:** Cards should be `surface_medium` with no shadow, defined by a 1px `surface_high` border.
- **Chips/Tags:** Monospaced typography (`label-sm`) inside a `surface_high` container with low-saturation versions of Primary or Secondary colors for categorization.
- **Lists:** Use subtle dividers (`rgba(255, 255, 255, 0.05)`) only when strictly necessary; otherwise, use whitespace to separate line items.
- **Code Blocks:** For technical research, use `surface_low` with a 2px left-accent border in Secondary Purple to distinguish code/data from prose.