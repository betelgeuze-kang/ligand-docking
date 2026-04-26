---
version: alpha
name: MD Evidence Desk
description: Design system for the local molecular dynamics delivery and evidence review viewer.
colors:
  primary: "#142F38"
  secondary: "#5D6F73"
  tertiary: "#9A5A16"
  neutral: "#F3EBDD"
  surface: "#FFF7EA"
  surface-strong: "#FFFCF5"
  line: "#D7C9B5"
  evidence-info: "#177E89"
  success: "#2F7D59"
  warning: "#A66512"
  danger: "#A6423A"
typography:
  h1:
    fontFamily: "IBM Plex Sans KR, Noto Sans KR, sans-serif"
    fontSize: 44px
    fontWeight: 700
    lineHeight: 1.02
    letterSpacing: -0.03em
  h2:
    fontFamily: "IBM Plex Sans KR, Noto Sans KR, sans-serif"
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: -0.02em
  body-md:
    fontFamily: "IBM Plex Sans KR, Noto Sans KR, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  label-caps:
    fontFamily: "IBM Plex Sans KR, Noto Sans KR, sans-serif"
    fontSize: 12px
    fontWeight: 700
    lineHeight: 1
    letterSpacing: 0.1em
rounded:
  sm: 12px
  md: 18px
  lg: 24px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  hero-panel:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral}"
    rounded: "{rounded.lg}"
    padding: 24px
  evidence-card:
    backgroundColor: "{colors.surface-strong}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: 18px
  data-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: 20px
  primary-action:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.surface-strong}"
    rounded: "{rounded.sm}"
    padding: 12px
  status-pill:
    backgroundColor: "{colors.surface-strong}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.sm}"
    padding: 8px
    height: 32px
  status-info:
    backgroundColor: "{colors.evidence-info}"
    textColor: "{colors.surface-strong}"
    rounded: "{rounded.sm}"
    padding: 8px
  status-success:
    backgroundColor: "{colors.success}"
    textColor: "{colors.surface-strong}"
    rounded: "{rounded.sm}"
    padding: 8px
  status-warning:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.surface-strong}"
    rounded: "{rounded.sm}"
    padding: 8px
  status-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.surface-strong}"
    rounded: "{rounded.sm}"
    padding: 8px
  rule-divider:
    backgroundColor: "{colors.line}"
    rounded: "{rounded.sm}"
    height: 1px
    width: 100%
---

## Overview

MD Evidence Desk makes the viewer feel like a local molecular-dynamics review bench: compact, technical, and ready for evidence handoff. The visual priority is explicit review hierarchy, not generic SaaS polish.

## Colors

Use deep ink for chrome and structure, warm ivory for reading surfaces, amber for primary local-delivery actions, cyan for molecular evidence and comparison focus, and clear success, warning, and danger colors for decision state. The light theme must remain in the same warm family rather than switching to blue-white defaults.

## Typography

Use IBM Plex Sans KR for Korean and English mixed labels, with Noto Sans KR and sans-serif fallbacks. Headings should feel editorial and dense; labels should read as technical metadata, with uppercase treatment reserved for short review wayfinding.

## Layout

Keep the viewer organized as top operations, left structure controls, central molecular scene and evidence overlays, and right comparison or blocker review. Dense panels should expose the current state first, then actions, then supporting evidence.

## Elevation & Depth

Use tonal layering, thin warm borders, and restrained shadows. Depth should clarify stacked panels and modals without creating glassy overlays that reduce chart, table, or molecule readability.

## Shapes

Use controlled rounded rectangles. Pills are for short status or review labels; larger radii belong to evidence panels and modal surfaces, not every small control.

## Components

Treat evidence cards, data panels, status pills, and primary actions as reusable primitives. Buttons must preserve existing hooks and IDs, but should visually separate local-delivery actions from passive review controls.

## Do's and Don'ts

- Do map these tokens into shared CSS variables before styling individual viewer regions.
- Do keep molecular evidence, blockers, and comparison outcomes visually distinct.
- Do preserve all existing DOM IDs, button text, emoji, and JavaScript hooks.
- Do keep light and dark themes in the same warm ivory and deep ink family.
- Don't reintroduce generic SaaS font or blue-default styling as the core identity.
- Don't hide critical review state behind hover-only affordances.
