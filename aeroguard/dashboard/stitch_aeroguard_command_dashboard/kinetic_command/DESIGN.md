# Design System Specification: Tactical Precision Interface

## 1. Overview & Creative North Star
**Creative North Star: "The Sovereign Command"**

This design system is engineered for mission-critical environments where split-second decisions meet absolute structural discipline. It rejects the "friendly" aesthetics of modern SaaS in favor of a high-fidelity, aerospace-grade command interface. 

The system breaks away from standard layouts through **calculated asymmetry** and **functional density**. We do not "fill space"; we "allocate coordinates." The interface should feel like a custom-milled piece of hardware: cold, precise, and authoritative. By utilizing thin weights, wide tracking, and a strictly monochromatic base punctuated by "Combustion" accents (burnt orange/copper), we create a hierarchy of extreme focus.

---

## 2. Colors & Tonal Architecture
The palette is rooted in low-reflectance surfaces to minimize eye fatigue during extended operations.

### Core Palette
- **Background (Base):** `#131314` (The void; deep matte)
- **Surface Tiers:**
    - `surface-container-lowest`: `#0e0e0f` (Sunken utility wells)
    - `surface-container`: `#201f20` (Standard module housing)
    - `surface-container-highest`: `#353436` (Active focal areas)
- **Primary (Combustion):** `#ffb68c` / `primary-container`: `#da7635` (Warning: Use only for high-priority interaction or critical status).

### The "No-Line" Rule & Sectioning
Traditional 1px borders are largely prohibited for sectioning. Instead, define boundaries through:
1.  **Background Shifts:** Use `surface-container-low` against `surface-core` to denote a sidebar or navigation rail.
2.  **Muted Grid Overlays:** Use `#1A1A1C` for a subtle 8px or 16px underlying grid visible only in the "gutters" between modules.
3.  **Tonal Transitions:** A transition from `#131314` to `#201f20` provides more structural integrity than a harsh line.

### The "Glass & Gradient" Rule
For HUD overlays or floating tactical panels, utilize **Glassmorphism**:
- **Background:** `surface-variant` at 60% opacity.
- **Backdrop Blur:** `12px` to `20px`.
- **Signature Gradient:** For primary actions, use a linear gradient from `primary` (#ffb68c) to `primary-container` (#da7635) at a 45-degree angle to simulate the glow of a physical filament.

---

## 3. Typography: Technical Authority
We use a dual-sans approach to balance data density with high-level navigation.

- **Display & Headlines (Space Grotesk):** Set to `300` or `400` weight. Always use `uppercase` with `letter-spacing: 0.15em`. This communicates a "read-out" feel.
- **Body & Data (Inter):** Chosen for its neutrality. Data tables should lean into `body-sm` or `label-md` to maximize information density.
- **Micro-Labels:** Use `label-sm` (`0.6875rem`) in `on-surface-variant` (#dcc1b4) for non-critical metadata, ensuring it recedes into the interface.

---

## 4. Elevation & Depth
In a mission-critical UI, "depth" represents "priority."

- **The Layering Principle:** Stack `surface-container-lowest` for the main workspace, and `surface-container-high` for interactive modules. This "negative" and "positive" stacking creates a tactile sense of hardware components.
- **Ambient Shadows:** Standard shadows are replaced by "Glow Falloffs." For floating modals, use a shadow color of `#da7635` (Primary Container) at `5%` opacity with a `40px` blur. It should look like an instrument light reflecting off a dark console.
- **The "Ghost Border" Fallback:** If a divider is mandatory for accessibility, use the `outline-variant` (#554339) at `30%` opacity. It must be `1px` or thinner.

---

## 5. Components

### Buttons
- **Primary:** Solid `primary` background, `on-primary` text. `0px` border-radius. High-contrast, immediate visibility.
- **Secondary:** `ghost-border` (outline-variant at 20%) with `uppercase` label. No fill.
- **Tertiary/Utility:** Text-only, `primary` color, with a `2px` underline that only appears on hover.

### Tactical Input Fields
- **State:** No rounded corners. Background: `surface-container-lowest`.
- **Active State:** A `1px` left-side accent line in `primary` (#ffb68c) rather than a full-box highlight.
- **Typography:** Use mono-spaced digits for numerical inputs to ensure vertical alignment in columns.

### Cards & Modules
- **Construction:** Forbid divider lines within cards. Separate header from body using a `2.5` (0.5rem) spacing gap or a subtle shift from `surface-container-high` to `surface-container`.
- **Headers:** Always `label-sm`, `uppercase`, with a subtle `noise texture` overlay in the background to suggest a physical screen material.

### Additional Aerospace Components
- **Data Brackets:** Use thin vector `L-shapes` at the corners of a selected container instead of a border. 
- **Status Beacons:** Small 4x4px squares. Static for "Nominal," Pulsing for "Active," and Sharp Flash for "Critical."

---

## 6. Do’s and Don’ts

### Do:
- **Maintain Discipline:** Keep all elements on a strict 4px grid.
- **Embrace Asymmetry:** Allow data-heavy columns to offset with minimal, high-breathability sidebars.
- **Use "Thin" Weights:** Stick to 300-400 weights to maintain the "etched" look.
- **Monospace Data:** Use `Roboto Mono` or `JetBrains Mono` for any changing coordinates or timestamps.

### Don’t:
- **No Curves:** Never exceed a `2px` radius. Ideally, stay at `0px`.
- **No Saturated Colors:** Avoid any blues, purples, or "startup" greens. 
- **No Standard Shadows:** Avoid heavy, black drop shadows that muddy the dark-mode aesthetic.
- **No Crowding:** Just because it's a command interface doesn't mean it should be cluttered. Use `spacing-16` (3.5rem) to separate major functional blocks.