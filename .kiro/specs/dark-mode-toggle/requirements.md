# Requirements Document

## Introduction

This feature adds a light/dark mode toggle to the Hi-Tech Waste Management Platform's top navigation bar (TopBar), positioned next to the search bar. The current application state — a teal/white sidebar and white main content area — is treated as **Light Mode**. **Dark Mode** inverts the palette to a dark slate background with light text and adjusted accent colours, covering every page, component, modal, widget, and UI element in the application. The user's preference is persisted across sessions.

**Important colour context:** The application currently uses a mixed palette — the TopBar is a teal gradient, the Sidebar is white with gray text, and page content areas use white backgrounds with gray/teal accents. Dark mode must invert all light surfaces (white → slate-900/slate-950), light text (gray-900 → gray-100), and light borders (gray-200 → slate-700) while keeping the teal brand accent readable in both modes.

## Glossary

- **Theme_Store**: The Zustand client-state store that holds and exposes the current theme value and toggle action.
- **Theme_Provider**: The React context provider component that reads the persisted theme on mount and applies the `dark` CSS class to the `<html>` element.
- **ThemeToggle**: The toggle button/switch component rendered inside the TopBar, next to the search bar.
- **Light_Mode**: The current application appearance — white/light-gray backgrounds, dark text, teal accents.
- **Dark_Mode**: The inverted appearance — slate-900/slate-950 backgrounds, light text, adjusted teal/emerald accents.
- **CSS_Variable**: A custom property defined in `globals.css` under `:root` (light) and `.dark` (dark) selectors, consumed by Tailwind's `hsl(var(--...))` tokens.
- **Tailwind_Dark_Variant**: The `dark:` prefix in Tailwind CSS that applies a utility class only when the `.dark` class is present on the `<html>` element.
- **localStorage**: The browser's persistent key-value storage used to save the user's theme preference under the key `hitech-theme`.
- **Transition**: A CSS `transition` property applied globally to smooth colour changes when switching themes.
- **WCAG_AA**: Web Content Accessibility Guidelines 2.1 Level AA contrast ratio requirements (minimum 4.5:1 for normal text, 3:1 for large text).

---

## Requirements

### Requirement 1: Theme Toggle Control in TopBar

**User Story:** As a platform user, I want a clearly visible toggle in the top navigation bar next to the search bar, so that I can switch between light and dark mode at any time without leaving my current page.

#### Acceptance Criteria

1. THE ThemeToggle SHALL be rendered in the TopBar component, positioned immediately to the right of the SearchBar and to the left of the NotificationBell.
2. THE ThemeToggle SHALL display a sun icon (Lucide `Sun`) when Dark_Mode is active and a moon icon (Lucide `Moon`) when Light_Mode is active, so the icon always indicates the mode the user will switch *to*.
3. WHEN the ThemeToggle is activated by a click or keyboard Enter/Space, THE Theme_Store SHALL toggle the theme between `light` and `dark`.
4. THE ThemeToggle SHALL be keyboard-focusable and SHALL display a visible focus ring that meets WCAG_AA contrast requirements.
5. THE ThemeToggle SHALL include an `aria-label` attribute that reads "Switch to dark mode" in Light_Mode and "Switch to light mode" in Dark_Mode.
6. THE ThemeToggle SHALL have a minimum touch target size of 32×32 px to meet mobile usability standards.

---

### Requirement 2: Theme State Management

**User Story:** As a platform user, I want my theme preference to be remembered, so that I do not have to re-select my preferred mode every time I open the application.

#### Acceptance Criteria

1. THE Theme_Store SHALL expose a `theme` value of type `'light' | 'dark'` and a `toggleTheme` action.
2. WHEN the application initialises, THE Theme_Provider SHALL read the stored value from `localStorage` under the key `hitech-theme` and initialise the Theme_Store with that value.
3. IF no value exists in `localStorage`, THEN THE Theme_Provider SHALL default to `'light'` (the current application appearance).
4. WHEN the theme changes, THE Theme_Store SHALL write the new value to `localStorage` under the key `hitech-theme`.
5. WHEN the theme changes, THE Theme_Provider SHALL add the class `dark` to the `<html>` element when Dark_Mode is active and remove it when Light_Mode is active.
6. THE Theme_Provider SHALL be mounted at the root layout level so that all pages and components inherit the theme class.

---

### Requirement 3: Global Dark Mode Colour Inversion

**User Story:** As a platform user, I want every part of the application to change appearance when I switch to dark mode, so that I never encounter a page or component that is still in the wrong theme.

#### Acceptance Criteria

1. WHEN Dark_Mode is active, THE application SHALL apply dark-mode CSS variable overrides in `globals.css` under the `.dark` selector so that all Tailwind `hsl(var(--...))` tokens resolve to dark-palette values.
2. WHEN Dark_Mode is active, THE Sidebar SHALL display a dark background (slate-900) with light navigation text (slate-200) and a dark border (slate-700/slate-800).
3. WHEN Dark_Mode is active, THE TopBar SHALL display a dark teal gradient (teal-900 to teal-800) or a slate-900 background that maintains brand identity.
4. WHEN Dark_Mode is active, THE main content area (`<main>`) SHALL display a slate-950 background instead of white.
5. WHEN Dark_Mode is active, all card components across every page SHALL display slate-800 backgrounds with slate-700 borders and slate-100/slate-200 text.
6. WHEN Dark_Mode is active, all modal and dialog components (Radix UI Dialog primitives) SHALL display slate-800 backgrounds with slate-700 borders.
7. WHEN Dark_Mode is active, all form inputs, selects, and textareas SHALL display slate-900 backgrounds with slate-700 borders and white text.
8. WHEN Dark_Mode is active, all data tables SHALL display slate-900 header backgrounds, slate-800 row backgrounds, slate-700 borders, and slate-200 text.
9. WHEN Dark_Mode is active, all dropdown menus and popover panels SHALL display slate-800 backgrounds with slate-700 borders and slate-100 text.
10. WHEN Dark_Mode is active, the NotificationPanel slide-over SHALL display a slate-900 background with slate-700 borders and slate-100 text.
11. WHEN Dark_Mode is active, the login page SHALL display a dark background consistent with the rest of the application.
12. WHEN Dark_Mode is active, all status badges SHALL maintain sufficient contrast against their dark backgrounds (WCAG_AA minimum 4.5:1 for normal text).

---

### Requirement 4: Smooth Theme Transition

**User Story:** As a platform user, I want the theme switch to feel polished and not jarring, so that the visual change is comfortable to the eye.

#### Acceptance Criteria

1. THE application SHALL apply a global CSS transition of `background-color 200ms ease, color 200ms ease, border-color 200ms ease` to all elements when the theme changes.
2. THE ThemeToggle icon SHALL animate with a rotation or fade transition of no more than 300ms when the theme is toggled.
3. WHEN the theme changes, THE page SHALL NOT flash a white or black screen before the new theme is applied (no flash of unstyled content).

---

### Requirement 5: Coverage of All Pages and Feature Modules

**User Story:** As a platform user, I want every page and module in the application to respect the active theme, so that there are no inconsistently styled screens.

#### Acceptance Criteria

1. THE dark mode styles SHALL apply to the Dashboard page and all its KPI cards, charts, and summary widgets.
2. THE dark mode styles SHALL apply to the Jobs pages (list, Kanban board, detail panel, and all job forms).
3. THE dark mode styles SHALL apply to the Fleet pages (vehicle list, map view, vehicle detail, maintenance calendar).
4. THE dark mode styles SHALL apply to the Weighbridge pages (records table, tonnage charts).
5. THE dark mode styles SHALL apply to the Compliance pages (scheduled waste batch table, consignment note forms, deadline calendar).
6. THE dark mode styles SHALL apply to the Recyclables, Destruction, BSF Farm, and Recycler Deliveries pages.
7. THE dark mode styles SHALL apply to the ESG & Carbon pages (carbon dashboard, diversion gauge, SDG alignment badges).
8. THE dark mode styles SHALL apply to the Finance pages (invoice list, payment tracking, revenue charts).
9. THE dark mode styles SHALL apply to the AI Assistant page (chat bubbles, agent status panel, alert feed).
10. THE dark mode styles SHALL apply to the Reports page and all generated report preview components.
11. THE dark mode styles SHALL apply to the Settings page and all settings sub-sections (user management, system configuration).
12. THE dark mode styles SHALL apply to the Clients pages (client list, client detail, client portal).
13. THE dark mode styles SHALL apply to the Labour, Equipment, and Disruptions pages.
14. WHEN Dark_Mode is active, Recharts chart components SHALL use dark-palette tooltip backgrounds (slate-800), dark grid lines (slate-700), and light axis labels (slate-400).
15. WHEN Dark_Mode is active, Leaflet map tiles SHALL remain unchanged (map tiles are third-party), but all map overlay UI elements (popups, controls) SHALL use dark-palette styles.

---

### Requirement 6: Accessibility and Contrast

**User Story:** As a platform user with visual accessibility needs, I want both light and dark modes to maintain readable contrast ratios, so that the application is usable regardless of the active theme.

#### Acceptance Criteria

1. WHEN Light_Mode is active, all text-on-background combinations SHALL meet WCAG_AA contrast ratio (minimum 4.5:1 for body text, 3:1 for large text and UI components).
2. WHEN Dark_Mode is active, all text-on-background combinations SHALL meet WCAG_AA contrast ratio (minimum 4.5:1 for body text, 3:1 for large text and UI components).
3. THE ThemeToggle icon SHALL have a minimum contrast ratio of 3:1 against the TopBar background in both Light_Mode and Dark_Mode.
4. IF a colour combination in Dark_Mode fails WCAG_AA contrast, THEN THE application SHALL use an adjusted colour that passes rather than a direct inversion of the light-mode colour.

---

### Requirement 7: No Regression on Existing Functionality

**User Story:** As a platform user, I want the theme toggle to be purely a visual change, so that no existing features, data, or interactions are broken by adding it.

#### Acceptance Criteria

1. WHEN the theme is toggled, THE application SHALL NOT trigger any API calls, data refetches, or state resets in TanStack Query.
2. WHEN the theme is toggled, THE application SHALL NOT unmount or remount any page-level components.
3. WHEN the theme is toggled, THE application SHALL NOT affect authentication state, session data, or navigation.
4. THE Theme_Store SHALL be independent of all other Zustand stores and SHALL NOT share or mutate any non-theme state.
5. WHEN the theme is toggled during an active WebSocket connection, THE WebSocket connection SHALL remain open and unaffected.
