# Resizing & Text Rendering Design Document

This document captures the design decisions for reworking the resizing logic and text rendering system in Piano MIDI Viewer.

**Status:** Implemented in v6.0.1
**Date:** 2026-01-25

---

## Core Principle

**Everything scales from a single anchor: white key width.**

This provides consistency and makes the code readable - every calculation starts with `white_key_width × ...`.

---

## Key Dimensions

All dimensions are derived from `white_key_width`:

```
white_key_width  = anchor (determined by window width / number of white keys)

white_key_height = white_key_width × height_ratio
                   where height_ratio ∈ [3, 6]

black_key_width  = white_key_width × 0.8
                   (increased from 0.7 to give more room for text)

black_key_height = white_key_width × height_ratio × 0.6
                   (60% of white key height, but expressed through the anchor)
```

---

## Text Gap

A single variable controls ALL text spacing:

```
text_gap = white_key_width × height_ratio × 0.05
```

This gap is used for:
- Distance from white key bottom edge to note letter
- Distance between note letter and octave number (on C keys)
- Distance from black key top edge to sharp
- Distance between sharp and flat (when both shown)
- Distance from last text element to the opposing edge (safety margin)

Starting value: 5% of white key height. Can be fine-tuned later.

---

## Text Positioning

### Horizontal
- ALL text is centered horizontally on its key

### White Keys (bottom to top)
- Note letter (C, D, E, F, G, A, B) at the bottom of ALL white keys
- Gap from bottom edge = text_gap
- Octave number ONLY on C keys, positioned above the note letter
- Gap between letter and number = text_gap

### Black Keys (top to bottom)
- Sharp (C♯, D♯, F♯, G♯, A♯) at the top
- Gap from top edge = text_gap
- Flat (D♭, E♭, G♭, A♭, B♭) below the sharp (when "Both" mode enabled)
- Gap between sharp and flat = text_gap

---

## Font Size Calculation

### Width Constraints

Font size is primarily determined by available horizontal space:

```
White keys: 1 character must fit in white_key_width × 0.7
Black keys: 2 characters must fit in white_key_width × 0.5
```

To calculate font size from width constraint:
1. Use a reference font size (e.g., 10pt)
2. Measure character width using QFontMetrics.horizontalAdvance()
3. Calculate: pixels_per_point = measured_width / reference_size
4. font_size = target_width / (num_chars × pixels_per_point)

### Height Constraints (Safety Caps)

To prevent overflow on wide-but-short windows, font size is also capped by vertical space:

**White keys - available space is bottom 40% (above black key region):**

```
If BOTH note names AND octave numbers are ON:
    max_font_height = ((white_key_width × height_ratio × 0.4) - (text_gap × 3)) / 2
    (Need: 3 gaps + 2 symbols)

If ONLY note names OR ONLY octave numbers:
    max_font_height = (white_key_width × height_ratio × 0.4) - (text_gap × 2)
    (Need: 2 gaps + 1 symbol)
```

**Black keys - available space is full black key height:**

```
If BOTH sharps AND flats are ON:
    max_font_height = ((white_key_width × height_ratio × 0.6) - (text_gap × 3)) / 2
    (Need: 3 gaps + 2 symbols, arranged as 2×2 grid)

If ONLY sharps OR ONLY flats:
    max_font_height = (white_key_width × height_ratio × 0.6) - (text_gap × 2)
    (Need: 2 gaps + 1 symbol)
```

### Final Font Size

```
white_key_font_size = min(width_based_size, height_based_size)
black_key_font_size = min(width_based_size, height_based_size)
```

One font size for ALL white keys, one font size for ALL black keys.

---

## Text Colors

Keep current behavior:
- Normal white key: black text
- Normal black key: white text
- Highlighted key: luminance-based contrast (black text on light backgrounds, white text on dark backgrounds)

---

## Settings Toggles

The system must support these settings (keep existing functionality):
- Show Octave Numbers (on/off)
- Show White Key Names (on/off)
- Show Black Key Names (on/off)
- Black Key Notation (Flats / Sharps / Both)

The height constraints adapt based on which settings are enabled.

---

## Minimum Font Size

```
MIN_FONT_SIZE = 6 points
```

If the calculated font size falls below 6pt, the text is not rendered (hidden). This prevents unreadable tiny text. Value may be adjusted after testing.

---

## Summary of Constants

```python
# Height ratio range (user adjusts by resizing window)
MIN_HEIGHT_RATIO = 3
MAX_HEIGHT_RATIO = 6

# Black key ratios (relative to white key)
BLACK_KEY_WIDTH_RATIO = 0.8      # was 0.7
BLACK_KEY_HEIGHT_RATIO = 0.6    # unchanged

# Text gap (relative to white key height)
TEXT_GAP_RATIO = 0.05           # 5% of white key height

# Text width constraints (relative to white key width)
WHITE_KEY_TEXT_WIDTH_RATIO = 0.7    # fit 1 char
BLACK_KEY_TEXT_WIDTH_RATIO = 0.5    # fit 2 chars

# Available vertical space ratios
WHITE_KEY_TEXT_AREA_RATIO = 0.4     # bottom 40% of white key
# Black key uses full black_key_height

# Minimum font size
MIN_FONT_SIZE = 6                   # points, hide text if smaller
```

---

## Implementation Notes

1. Remove or simplify existing complex resizing logic
2. Ensure no leftover code creates bugs
3. All calculations flow from white_key_width
4. Use QFontMetrics for accurate text measurement
5. Font is JetBrains Mono (monospace) - all characters same width
6. Test with extreme window proportions (very wide, very tall, very small)
