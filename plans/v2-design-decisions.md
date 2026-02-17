# V2 Design Decisions: Mac/Braun/Tufte Principles

## Core Philosophy

**V1 Problem:** Corporate branding theater (navy gradients, gold accents, visual noise)  
**V2 Goal:** Maximize information, minimize decoration — like a Braun radio or original Mac UI

---

## Design Decisions

### Decision 1: Typography

**Problem:** DM Sans is trendy but adds no clarity  
**Options:**
- A: Keep DM Sans (branded feel)
- B: System fonts (SF Pro / Segoe UI / -apple-system)
- C: Helvetica Neue (classic, consistent)

**Recommendation: B (System fonts)**

**Why:**
- Renders instantly (no web font loading)
- Optimized for each OS
- Tufte principle: "Use the best typeface available"
- Courier New for monospace (honest, not trendy)

```css
--sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
--mono: "Courier New", Courier, monospace;
```

---

### Decision 2: Color Palette

**Problem:** Navy (#1A1F71) + gold (#F7B600) is Visa branding, not functional  
**Options:**
- A: Keep Visa brand colors
- B: Grayscale only (black, white, grays)
- C: Minimal color (black/white + single accent for actions)

**Recommendation: C (Black/white + blue for actions)**

**Why:**
- Black (#000) on white (#fff) = maximum contrast (Tufte)
- Single blue (#007aff) for clickable elements (iOS convention)
- Green ✓ / amber ⚠ / red ✗ only for status (semantic meaning)
- No decorative colors

```css
--text: #000;
--bg: #fff;
--border: #d1d1d6;  /* iOS-style subtle gray */
--action: #007aff; /* iOS blue */
--green: #34c759;
--amber: #ff9500;
--red: #ff3b30;
```

---

### Decision 3: Layout & Spacing

**Problem:** Current 880px max-width feels arbitrary  
**Options:**
- A: 880px (keeps current)
- B: 960px (classic grid)
- C: 720px (optimal reading width, Tufte)

**Recommendation: C (720px)**

**Why:**
- 66 characters per line = ideal for readability
- Forces information density
- Breathing room on large screens
- 24px spacing unit (Apple's 8pt grid × 3)

```css
.wrap { max-width: 720px; margin: 0 auto; padding: 0 24px; }
```

---

### Decision 4: Header

**Problem:** Gradient header with gold accent is visual weight for no reason  
**Options:**
- A: Keep gradient + gold accent
- B: Solid white header with gray border
- C: No header, just page title

**Recommendation: B (Minimal header)**

**Why:**
- White background = consistency
- 1px bottom border = subtle separation
- "Visa Data Access" in system font, black text
- No visual weight, just information

```
┌────────────────────────────────┐
│ Visa Data Access               │  ← Simple, black text
├────────────────────────────────┤
│                                │
│ [Request workflow view]        │
```

---

### Decision 5: Cards & Borders

**Problem:** Drop shadows + rounded corners = decoration  
**Options:**
- A: Keep shadows + 10px border radius
- B: 1px solid borders, no radius
- C: 1px borders, 2px radius (subtle)

**Recommendation: C (1px borders, minimal radius)**

**Why:**
- 1px border = clear boundary (Braun)
- 2px radius = not harsh, not decorative
- No shadows = honest depth
- Light gray border (#d1d1d6) not black

```css
.card {
  border: 1px solid #d1d1d6;
  border-radius: 2px;
  background: #fff;
}
```

---

### Decision 6: Buttons & Affordances

**Problem:** Button looks pretty but unclear if disabled  
**Options:**
- A: Gradient buttons (current)
- B: Solid blue button, gray when disabled
- C: Borderless button (iOS style)

**Recommendation: B (Solid blue, clear states)**

**Why:**
- Blue = "this is clickable" (iOS convention)
- Gray = disabled (40% opacity)
- Hover: darker blue (#0051d5)
- Active: even darker (#004bb8)
- **Clear affordance** - you know what's interactive

```css
.btn {
  background: #007aff;
  color: #fff;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
}
.btn:hover { background: #0051d5; }
.btn:active { background: #004bb8; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
```

---

### Decision 7: Agent Cards

**Problem:** Colored dots + gradient tags = visual noise  
**Options:**
- A: Keep colored dots + gradient tags
- B: No dots, just agent name + gray tag
- C: Emoji icons (🤖 for LLM, ⚙️ for ABAC)

**Recommendation: B (Text only, gray tags)**

**Why:**
- Agent name is the information
- Tag shows execution type (Claude Sonnet / Python ABAC)
- No color = no distraction
- Gray box = "this is metadata"

```
┌──────────────────────────────────────┐
│ Intake Agent       Claude Sonnet 3ms │
├──────────────────────────────────────┤
│ requester: analyst@visa.com          │
│ dataset: fraud_detection_models      │
│ access_level: read ✓                 │
└──────────────────────────────────────┘
```

---

### Decision 8: ABAC Policy Checks

**Problem:** 4-column grid is dense but hard to scan  
**Options:**
- A: Keep 4 columns (policy | req | → | user)
- B: 2 rows per check (requirement on top, user below)
- C: List format with checkmarks

**Recommendation: C (List format)**

**Why:**
- Easier to scan
- Clear ✓ or ✗ at the end
- Requirement and user value on same line with →
- Like a checklist (familiar pattern)

```
ABAC Policy Checks:

✓ Role Authorization
  Requirement: [Data Analyst, Senior Data Analyst]
  User: Senior Data Analyst

✓ Clearance Level
  Requirement: Minimum Level 2
  User: Level 3 (verified)

✗ Access Level Restriction
  Requirement: READ requests auto-approve
  User: Requesting WRITE access
```

---

### Decision 9: Receipt Format

**Problem:** Email address doesn't tell you who made the request  
**Options:**
- A: WHO: analyst@visa.com (current)
- B: WHO: Sarah Chen (analyst@visa.com)
- C: WHO: Sarah Chen | Senior Data Analyst | analyst@visa.com

**Recommendation: C (Name | Role | Email)**

**Why:**
- Name = primary (who you know)
- Role = context (why they might need it)
- Email = identifier (for lookup)
- Pipe separator = clean Tufte style

```
DECISION: APPROVED

WHO: Sarah Chen | Senior Data Analyst | analyst@visa.com
WHAT: fraud_detection_models (READ access)
REASON: Analyze Q1 false positive rates...
```

---

### Decision 10: Stepper/Timeline

**Problem:** Stepper at top + timeline below = redundant  
**Options:**
- A: Keep both
- B: Remove stepper, just timeline
- C: Condensed: just show agent cards, no timeline rail

**Recommendation: C (Just agent cards)**

**Why:**
- Cards already show sequence (top to bottom)
- No need for visual rail
- More space for information
- Simpler = better (Rams' 10th principle)

---

## Visual Spec (V2)

| Element | Value |
|---------|-------|
| Font body | System (-apple-system, Segoe UI) |
| Font mono | Courier New |
| Text color | #000 |
| Background | #fff |
| Border | #d1d1d6 (1px) |
| Action blue | #007aff |
| Status green | #34c759 |
| Status amber | #ff9500 |
| Status red | #ff3b30 |
| Border radius | 2px (minimal) |
| Max width | 720px |
| Spacing unit | 24px |

## What Changes

### Removed:
- Navy/gold Visa branding
- Gradient backgrounds
- Drop shadows
- Colored dots on cards
- Stepper rail
- Rounded corners (10px → 2px)
- Web fonts (DM Sans)

### Added:
- System fonts
- Clear hover states
- More whitespace
- Honest materials (black on white)
- Name + role in WHO field
- Simpler visual hierarchy

## Success Metrics

1. **Information density**: More data visible without scrolling
2. **Scannability**: Can find key info (WHO/WHAT/DECISION) in <2 seconds
3. **Affordances**: Clear what's clickable (blue) vs status (green/red)
4. **Timeless**: No trendy gradients, will age well

---

## Implementation Notes

- Start with demo-prototype-v2.html
- Keep same functionality, just restyled
- Test on Mac (SF Pro), Windows (Segoe UI), Linux (system-ui)
- Ensure receipt format shows Name | Role | Email
