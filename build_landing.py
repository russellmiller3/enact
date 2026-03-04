import re

with open('index.html', 'r', encoding='utf-8') as f:
    index_html = f.read()

# Extract styles
styles_match = re.search(r'<style>(.*?)</style>', index_html, re.DOTALL)
styles = styles_match.group(1) if styles_match else ""

# Modify styles for themes
styles = styles.replace("""        :root {
            --bg:       #0b1020;
            --surface:  #131b2e;
            --border:   #2a3447;
            --text:     #ffffff;
            --muted:    #94a3b8;
            --subtle:   #64748b;
            --accent:   #4A6FA5;
            --accent-d: #3d5a85;
            --green:    #059669;
            --red:      #dc2626;
            --amber:    #d97706;
            --mono: 'IBM Plex Mono', 'Courier New', monospace;
            --sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }""", """        :root {
            --green:    #059669;
            --red:      #dc2626;
            --amber:    #d97706;
            --mono: 'IBM Plex Mono', 'Courier New', monospace;
            --sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        [data-theme="dark"] {
            --bg:       #0b1020;
            --surface:  #131b2e;
            --border:   #2a3447;
            --text:     #ffffff;
            --muted:    #94a3b8;
            --subtle:   #64748b;
            --accent:   #4A6FA5;
            --accent-d: #3d5a85;
        }
        [data-theme="light"] {
            --bg:       #ffffff;
            --surface:  #f8fafc;
            --border:   #e2e8f0;
            --text:     #0f172a;
            --muted:    #475569;
            --subtle:   #94a3b8;
            --accent:   #2563eb;
            --accent-d: #1d4ed8;
        }""")

# Add theme toggle button style
styles += """
        .theme-toggle {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 14px;
            cursor: pointer;
            color: var(--muted);
            font-family: var(--mono);
            transition: all 0.2s;
        }
        .theme-toggle:hover { border-color: var(--accent); color: var(--text); }
"""

# Extract sections to keep
def extract_section(html, start_marker, end_marker):
    pattern = re.compile(f'{start_marker}(.*?){end_marker}', re.DOTALL)
    match = pattern.search(html)
    return match.group(1) if match else ""

quickstart = extract_section(index_html, r'<!-- ═══════════════════════════════════════════════════\s*QUICKSTART\s*════════════════════════════════════════════════════ -->', r'<!-- ═══════════════════════════════════════════════════\s*MIGRATION')
migration = extract_section(index_html, r'<!-- ═══════════════════════════════════════════════════\s*MIGRATION — ALREADY HAVE AN AGENT\?\s*════════════════════════════════════════════════════ -->', r'<!-- ═══════════════════════════════════════════════════\s*POLICY REFERENCE')
policies = extract_section(index_html, r'<!-- ═══════════════════════════════════════════════════\s*POLICY REFERENCE\s*════════════════════════════════════════════════════ -->', r'<!-- ═══════════════════════════════════════════════════\s*RECEIPT DEMO')
receipt_demo = extract_section(index_html, r'<!-- ═══════════════════════════════════════════════════\s*RECEIPT DEMO\s*════════════════════════════════════════════════════ -->', r'<!-- ═══════════════════════════════════════════════════\s*WORKFLOW LIBRARY')
hitl = extract_section(index_html, r'<!-- ═══════════════════════════════════════════════════\s*HUMAN-IN-THE-LOOP\s*════════════════════════════════════════════════════ -->', r'<section id="roadmap">')
roadmap = extract_section(index_html, r'<section id="roadmap">', r'<!-- ═══════════════════════════════════════════════════\s*PRICING')

# Update headers in kept sections
policies = policies.replace('<h2>30 policies, shipped today</h2>', '<h2>20+ production policies. Ship on day one.</h2>')
hitl = hitl.replace('<div class="section-label">Human-in-the-Loop</div>', '<div class="section-label">Governance primitive: human approval for high-risk ops.</div>')

# Build new HTML
new_html = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enact — Governed, Auditable, Reversible AI Agents</title>
    <style>
""" + styles + """
    </style>
</head>
<body>

<header>
    <div class="container">
        <div class="header-inner">
            <div class="logo">enact</div>
            <button class="nav-toggle" onclick="document.querySelector('nav').classList.toggle('open')">
                <span></span>
                <span></span>
                <span></span>
            </button>
            <nav>
                <a href="#quickstart">Quickstart</a>
                <a href="#migrate">Migrate</a>
                <a href="#policies">Policies</a>
                <a href="#roadmap">Roadmap</a>
                <a href="#pricing">Pricing</a>
                <a href="https://github.com/russellmiller3/enact">GitHub</a>
                <button class="theme-toggle" onclick="toggleTheme()">Toggle Theme</button>
                <a href="mailto:hello@enact.cloud?subject=Early Access" class="nav-cta">Get Audit-Ready →</a>
            </nav>
        </div>
    </div>
</header>

<section class="hero">
    <div class="container">
        <h1>Make your AI agents governed,<br>auditable, and reversible.</h1>
        <p class="sub">
            Enact is the action governance layer for AI agents. Every action is policy-checked before it runs, logged as a signed receipt, and — when something slips through — rolled back in one command. Ship agents to production without blowing up your SOC2, HIPAA, or ISO-27001 story.
        </p>
        <div class="cta-row">
            <a href="#quickstart" class="btn btn-primary">Get audit-ready in a day</a>
            <a href="https://github.com/russellmiller3/enact" class="btn btn-secondary">Install the open-source SDK →</a>
        </div>
        <p class="hero-note">Open source core · Self-host free · Cloud from $49/month · No credit card to start</p>
    </div>
</section>

<!-- QUICKSTART -->
""" + quickstart + """

<section class="alt">
    <div class="container centered">
        <div class="section-label">Why You Need This</div>
        <h2>Your agents are running blind. So are you.</h2>
        
        <div class="problem-grid" style="margin-top: 48px;">
            <div class="problem-card">
                <h3>1. No policy enforcement</h3>
                <p>There's no code that says "don't drop a table outside a maintenance window" or "don't bulk-email every customer from a draft." Every agent is one bad prompt away from a live incident.</p>
            </div>
            <div class="problem-card">
                <h3>2. No audit trail</h3>
                <p>When your auditor, VP, or CISO asks "what did the agent actually do?" — you're digging through CloudWatch at 2am. No searchable log. No compliance path. No proof.</p>
            </div>
            <div class="problem-card">
                <h3>3. No human-in-the-loop</h3>
                <p>High-risk actions run without any human seeing them first. If your agent decides to delete rows, merge to main, or message a thousand customers — nothing stops it.</p>
            </div>
            <div class="problem-card">
                <h3>4. No rollback</h3>
                <p>When something slips through, you're restoring from backups, manually reconstructing state, and explaining it to stakeholders. There is no undo.</p>
            </div>
        </div>
    </div>
</section>

<section>
    <div class="container centered">
        <div class="section-label">What Happens Without Enact</div>
        <h2>This isn't hypothetical.</h2>
        
        <div class="disaster-incidents" style="margin-top: 48px;">
            <div class="incident">
                <div class="incident-tag">Production incident · 13 hours down</div>
                <h3>Amazon Kiro Agent — AWS Outage</h3>
                <p>An AI agent optimizing resource allocation had broader permissions than anyone realized. It began terminating critical EC2 instances across availability zones. No human approval. No safety check. Cascading failures took down major services for 13 hours.</p>
                <p class="root">Root cause: "The agent should never have had write access to production compute resources."</p>
            </div>
            <div class="incident">
                <div class="incident-tag">Data loss · Customer records gone</div>
                <h3>Replit Agent — Deleted Production Database</h3>
                <p>An AI agent doing "database maintenance" identified what it thought were unused tables and deleted them. They were critical production tables. The agent generated plausible explanations for why the deletion was safe. The data was gone.</p>
                <p class="root">Root cause: Full write access to production schema. No approval workflow. No audit trail.</p>
                <p style="margin-top: 12px; font-size: 13px; color: var(--accent);"><strong>With Enact:</strong> pre-action row capture means <code>enact.rollback(run_id)</code> restores every deleted record in one command — with a signed rollback receipt showing exactly what was reversed and what couldn't be.</p>
            </div>
        </div>
    </div>
</section>

<section class="alt">
    <div class="container centered">
        <div class="section-label">How Enact Works</div>
        <h2>One layer. Four things every production agent needs.</h2>
        
        <div class="problem-grid" style="grid-template-columns: repeat(2, 1fr); margin-top: 48px;">
            <div class="problem-card">
                <h3 style="color: var(--accent);">Block 1: Policy-gated execution</h3>
                <p>Deterministic Python functions run before agents touch anything real. No LLMs. No guesswork. Versioned in Git. Testable with pytest. 20+ policies ship out of the box — or write your own in 10 lines.</p>
            </div>
            <div class="problem-card">
                <h3 style="color: var(--accent);">Block 2: Signed receipts on every run</h3>
                <p>Every action — allowed or blocked — generates a cryptographically signed receipt: agent identity, action, resource, policy result, timestamp, model version. Searchable. Exportable. Auditor-ready.</p>
            </div>
            <div class="problem-card">
                <h3 style="color: var(--accent);">Block 3: Human-in-the-loop for high-risk ops</h3>
                <p>High-risk actions pause and wait for human approval before running. Signed email link, one-time-use, auto-expire. The approver needs no login. Agent gets a signed PASS or BLOCK receipt either way.</p>
            </div>
            <div class="problem-card">
                <h3 style="color: var(--accent);">Block 4: One-command rollback</h3>
                <p><code>enact.rollback(run_id)</code> reverses what it can (DB rows, files, branches, open PRs, Slack messages), explicitly records what it can't (pushed commits), and generates a signed rollback receipt. Your undo button — with honest limits.</p>
            </div>
        </div>
    </div>
</section>

<!-- MIGRATION -->
""" + migration + """

<!-- POLICIES -->
""" + policies + """

<!-- RECEIPT DEMO -->
""" + receipt_demo + """

<!-- HITL -->
""" + hitl + """

<section>
    <div class="container centered">
        <div class="section-label">Compliance & Audit</div>
        <h2>Turn every agent run into a compliance artifact.</h2>
        
        <div style="max-width: 700px; margin: 0 auto; text-align: left; margin-top: 48px;">
            <p style="font-size: 16px; color: var(--muted); margin-bottom: 24px;">Your agents are already running. Every action is already happening. The question is whether you can <em>prove</em> it to an auditor — and whether your controls are documented and defensible.</p>
            <p style="font-size: 16px; color: var(--muted); margin-bottom: 24px;">Enact makes that automatic:</p>
            <ul style="list-style: none; margin-bottom: 32px;">
                <li style="display: flex; gap: 12px; font-size: 15px; margin-bottom: 12px; line-height: 1.6;"><span style="color: var(--green); font-weight: 700;">✓</span> Every action is signed, timestamped, and attributed to a specific agent, user, and policy version.</li>
                <li style="display: flex; gap: 12px; font-size: 15px; margin-bottom: 12px; line-height: 1.6;"><span style="color: var(--green); font-weight: 700;">✓</span> Generate SOC2, ISO 27001, or HIPAA audit reports directly from your receipt database. One click. Hand it to your auditor, not your engineers.</li>
                <li style="display: flex; gap: 12px; font-size: 15px; margin-bottom: 12px; line-height: 1.6;"><span style="color: var(--green); font-weight: 700;">✓</span> Policy definitions are versioned in Git — your "controls documentation" writes itself.</li>
            </ul>
            <div style="background: var(--surface); border-left: 4px solid var(--accent); padding: 20px; border-radius: 0 8px 8px 0;">
                <p style="font-size: 15px; color: var(--muted); margin: 0;">40 hours of engineering time explaining "what did agents do" to an auditor costs you $10,000+. Enact turns that into a 10-minute export.</p>
            </div>
        </div>
    </div>
</section>

<!-- ROADMAP -->
<section id="roadmap">
""" + roadmap + """

<section class="alt" id="pricing">
    <div class="container centered">
        <div class="section-label">Pricing</div>
        <h2>Start free. Pay as your agents do more.</h2>
        
        <div class="pricing-grid" style="grid-template-columns: repeat(4, 1fr); max-width: 1200px; margin-top: 48px;">
            <!-- Tier 0 -->
            <div class="pricing-card">
                <h3>Tier 0 — Open Source</h3>
                <div class="price">Free</div>
                <div class="price-sub">forever</div>
                <ul class="feature-list">
                    <li><span class="fi fi-check">✓</span> Self-hosted Enact core</li>
                    <li><span class="fi fi-check">✓</span> Local receipt database and UI (<code>enact-ui</code>)</li>
                    <li><span class="fi fi-check">✓</span> Policy enforcement and rollback</li>
                    <li><span class="fi fi-check">✓</span> Unlimited everything — run it yourself</li>
                </ul>
                <div style="background: var(--bg); padding: 8px; border-radius: 6px; font-family: var(--mono); font-size: 12px; margin-bottom: 16px; border: 1px solid var(--border);">pip install enact-sdk</div>
                <a href="https://github.com/russellmiller3/enact" class="pricing-btn">Get started →</a>
            </div>

            <!-- Tier 1 -->
            <div class="pricing-card">
                <h3>Tier 1 — Starter</h3>
                <div class="price">$49<span style="font-size: 16px; font-weight: 400; color: var(--muted);">/mo</span></div>
                <div class="price-sub">or $490/year — 2 months free<br><br>For solo devs and small teams shipping their first production agents.</div>
                <ul class="feature-list">
                    <li><span class="fi fi-check">✓</span> Cloud receipt storage up to 50,000 receipts/month</li>
                    <li><span class="fi fi-check">✓</span> 1 environment (prod or staging)</li>
                    <li><span class="fi fi-check">✓</span> Email-based HITL up to 100 approvals/month</li>
                    <li><span class="fi fi-check">✓</span> Cloud UI: searchable receipt browser</li>
                    <li><span class="fi fi-check">✓</span> Basic CSV audit export</li>
                    <li><span class="fi fi-dash">−</span> Overages: $0.50 per additional 10,000 receipts</li>
                </ul>
                <a href="mailto:hello@enact.cloud?subject=Starter Plan" class="pricing-btn">Start free trial →</a>
            </div>

            <!-- Tier 2 -->
            <div class="pricing-card featured">
                <div class="featured-badge">RECOMMENDED</div>
                <h3>Tier 2 — Team</h3>
                <div class="price">$249<span style="font-size: 16px; font-weight: 400; color: var(--muted);">/mo</span></div>
                <div class="price-sub">or $2,490/year — 2 months free<br><br>For teams running agents in production and starting to get compliance questions.</div>
                <ul class="feature-list">
                    <li><span class="fi fi-check">✓</span> Cloud receipt storage up to 500,000 receipts/month</li>
                    <li><span class="fi fi-check">✓</span> 3 environments (dev / staging / prod)</li>
                    <li><span class="fi fi-check">✓</span> Unlimited HITL approvals</li>
                    <li><span class="fi fi-check">✓</span> Pre-built industry policy packs: FinTech, Healthcare, DevOps</li>
                    <li><span class="fi fi-check">✓</span> SOC2 / ISO 27001 audit export builder (standard templates)</li>
                    <li><span class="fi fi-check">✓</span> Email support</li>
                    <li><span class="fi fi-dash">−</span> Overages: $1 per additional 100,000 receipts</li>
                </ul>
                <a href="mailto:hello@enact.cloud?subject=Team Plan" class="pricing-btn primary">Start free trial →</a>
            </div>

            <!-- Tier 3 -->
            <div class="pricing-card">
                <h3>Tier 3 — Professional</h3>
                <div class="price">$750<span style="font-size: 16px; font-weight: 400; color: var(--muted);">/mo</span></div>
                <div class="price-sub">or $9,000/year<br><br>For mid-market teams who need full governance controls and compliance artifacts.</div>
                <ul class="feature-list">
                    <li><span class="fi fi-check">✓</span> Cloud receipt storage up to 5,000,000 receipts/month</li>
                    <li><span class="fi fi-check">✓</span> Unlimited environments</li>
                    <li><span class="fi fi-check">✓</span> SSO, SAML, RBAC</li>
                    <li><span class="fi fi-check">✓</span> Full audit report builder: SOC2, ISO 27001, HIPAA templates</li>
                    <li><span class="fi fi-check">✓</span> Anomaly detection: flag agents acting outside normal behavior</li>
                    <li><span class="fi fi-check">✓</span> Basic SLAs</li>
                    <li><span class="fi fi-check">✓</span> Slack support</li>
                    <li><span class="fi fi-dash">−</span> Overages: contact us</li>
                </ul>
                <a href="mailto:hello@enact.cloud?subject=Professional Plan" class="pricing-btn">Start free trial →</a>
            </div>
        </div>

        <div style="margin-top: 48px; padding: 28px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; max-width: 800px; margin-left: auto; margin-right: auto; text-align: left;">
            <h3 style="font-size: 18px; margin-bottom: 8px;">Tier 4 — Enterprise (Starting at $25,000 / year)</h3>
            <p style="font-size: 14px; color: var(--muted); margin-bottom: 16px;">For regulated industries, large agent fleets, and teams where governance isn't optional.</p>
            <ul style="list-style: none; margin-bottom: 24px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                <li style="display: flex; gap: 8px; font-size: 13px;"><span style="color: var(--green);">✓</span> Custom receipt volume (typically 10M+/month)</li>
                <li style="display: flex; gap: 8px; font-size: 13px;"><span style="color: var(--green);">✓</span> Custom data retention (up to 7 years)</li>
                <li style="display: flex; gap: 8px; font-size: 13px;"><span style="color: var(--green);">✓</span> Custom policy packs and implementation support</li>
                <li style="display: flex; gap: 8px; font-size: 13px;"><span style="color: var(--green);">✓</span> On-prem or hybrid deployment</li>
                <li style="display: flex; gap: 8px; font-size: 13px;"><span style="color: var(--green);">✓</span> Dedicated customer success manager</li>
                <li style="display: flex; gap: 8px; font-size: 13px;"><span style="color: var(--green);">✓</span> Priority SLAs and on-call support</li>
                <li style="display: flex; gap: 8px; font-size: 13px; grid-column: 1 / -1;"><span style="color: var(--green);">✓</span> Custom audit templates and regulatory mapping (EU AI Act, ISO 42001)</li>
            </ul>
            <a href="mailto:hello@enact.cloud?subject=Enterprise" class="btn btn-secondary">Talk to us →</a>
        </div>

        <p style="margin-top: 32px; font-size: 14px; color: var(--subtle);">The Kiro outage cost millions. The Replit deletion was career-limiting. Preventing one incident pays for Enact for years.</p>
    </div>
</section>

<section class="footer-cta">
    <div class="container">
        <h2>Your agents are in production.<br>Are you in control?</h2>
        <p>Add Enact in minutes. Know what your agents did, enforce what they're allowed to do, and prove it to anyone who asks.</p>
        <div class="cta-row">
            <a href="https://github.com/russellmiller3/enact" class="btn btn-primary">Install the SDK free</a>
            <a href="mailto:hello@enact.cloud?subject=Early Access" class="btn btn-secondary">Start cloud trial — $49/month</a>
        </div>
    </div>
</section>

<footer>
    <div class="container">
        <p>Built for engineers who can't afford to find out what happens when an agent goes off-script.</p>
        <p style="margin-top: 8px;">© 2026 Enact · Open source · Audit-trail ready · <a style="color: var(--accent);" href="https://github.com/russellmiller3/enact">GitHub</a></p>
    </div>
</footer>

<script>
    // Theme toggle
    function toggleTheme() {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    }

    // Load saved theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }

    // Mobile nav close on link click
    document.querySelectorAll('nav a').forEach(link => {
        link.addEventListener('click', () => {
            document.querySelector('nav').classList.remove('open');
        });
    });

    function showTab(name) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        document.getElementById('tab-' + name).classList.add('active');
        event.target.classList.add('active');
    }
</script>

<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
<script>lucide.createIcons();</script>
</body>
</html>
"""

with open('new-landing.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print("Successfully built new-landing.html")
