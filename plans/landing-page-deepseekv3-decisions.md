# Enact Landing Page: DeepSeek v3 Optimization

> Goal: Create shorter, lighter landing page optimized for trial conversion

## Design Principle: Information Hierarchy for ICPs

**Core tension:** Comprehensive technical detail vs. conversion-focused brevity
**Resolution:** Prioritize sections that drive trial signups, cut everything else

## Decision 1: Which Sections to Cut

### The Problem
The current landing page is 1297 lines with 15+ sections. Most visitors won't read past the first 3 screens. We need to ruthlessly prioritize.

### Option A: Keep Everything, Just Lighter
```
[Current structure]
- Hero
- 3-pillar strip  
- Framework compat
- MCP positioning
- Disasters
- Migration
- Quickstart
- Policy reference
- Receipt demo
- Workflow library
- OSS vs cloud
- Roadmap
- Pricing
- Footer CTA
```
**Pros:** Complete information, covers all objections
**Cons:** Overwhelming, high bounce rate, poor conversion

### Option B: Aggressive Cut to Core Value
```
[Optimized structure]
- Hero (value prop + CTA)
- 3-pillar strip (what it does)
- Quickstart (how it works)
- Receipt demo (proof it works)
- Pricing (what it costs)
- Footer CTA (final push)
```
**Pros:** Focused, higher conversion, respects attention span
**Cons:** Loses some technical detail

### **Recommendation: Option B**

**Why:**
- ADHD-optimized because it reduces cognitive load to just 5 key sections
- Concrete benefit: Higher trial conversion (visitors see value faster)
- Concrete benefit: Lower bounce rate (less overwhelming)

**Later enhancement:** Add progressive disclosure for technical users who want more detail

## Decision 2: Color Scheme Optimization

### The Problem
Text is too dark on black background (#94a3b8 on #0b1020 = 4.5:1 contrast ratio, below WCAG AA)

### Option A: Lighter Text Colors
- Change --muted from #94a3b8 to #cbd5e1
- Change --subtle from #64748b to #94a3b8  
- Keep dark background for security/tech vibe

### Option B: Light Mode Switch
- Add dark/light toggle
- Default to improved dark scheme
- Let users choose

### **Recommendation: Option A**

**Why:**
- ADHD-optimized because better contrast reduces eye strain
- Concrete benefit: WCAG AA compliance (4.5:1+)
- Concrete benefit: Maintains security/tech aesthetic

## Decision 3: DeepSeek v3 Specific Optimizations

### The Problem
Generic landing page vs. tailored for AI/ML engineering audience

### Option A: Add AI-Specific Language
- "Stop your AI agents from doing dumb sh*t" → "Governance for AI agents"
- Emphasize MCP/tool_use integration
- Use AI engineering terminology

### Option B: Keep General but Improve Clarity
- Maintain current voice but improve readability
- Focus on universal pain points

### **Recommendation: Option A**

**Why:**
- ADHD-optimized because specific language resonates better with target audience
- Concrete benefit: Higher relevance for AI/ML engineers
- Concrete benefit: Better positioning against competitors

## Decision 4: Hosting and Infrastructure

### The Problem
Need a reliable, fast, and low-maintenance hosting solution for the static landing page that can scale to a cloud backend later.

### Option A: Traditional Shared Hosting (Porkbun/NearlyFreeSpeech)
- **Cost:** ~$2.50 - $7.50 / month
- **Pros:** Integrated with domain registrar
- **Cons:** Slower, manual deployment, paid from day one

### Option B: Modern Static Hosting (Vercel/Netlify)
- **Cost:** $0 (Free tier)
- **Pros:** Global CDN, auto-deploy from GitHub, free SSL, extremely fast
- **Cons:** Requires separate DNS configuration

### **Recommendation: Option B (Vercel)**

**Why:**
- **ADHD-optimized** because it automates the deployment process (push to git = live site). No manual FTP or file uploads.
- **Concrete benefit:** $0 starting cost.
- **Concrete benefit:** Superior performance via global edge network.
- **Future-proofing:** Easy transition to a Python/FastAPI backend on Railway/Render while keeping the frontend on Vercel.

## Implementation Plan

1. **Phase 1:** Cut sections (keep only hero, pillars, quickstart, receipt, pricing, footer)
2. **Phase 2:** Improve color contrast and typography
3. **Phase 3:** Add DeepSeek-specific language and positioning
4. **Phase 4:** Test with real users for conversion optimization

**File:** `landing_page_deepseekv3.html`