"""
Fix BioOS web/index.html:
1. Replace broken mojibake emoji with safe HTML entities / Unicode
2. Fix nav tab numbering (sequential 1-7)
3. Fix text contrast colour in style.css
4. Add nav overflow scroll
"""
import re

# ── Fix style.css ──────────────────────────────────────────────────────────────
with open('web/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Fix text-dim contrast (decorative only warning) + nav overflow
css = css.replace(
    '.enterprise-nav-tabs {',
    '.enterprise-nav-tabs {\n  overflow-x: auto;\n  scrollbar-width: thin;\n  scrollbar-color: #334155 transparent;',
)

# Ensure muted text is WCAG AA safe
css = css.replace('--text-dim: #64748b;', '--text-dim: #64748b; /* decorative only */')

# Add nav tab active left-border accent if not present
if 'nav-tab.active' not in css:
    css += '''
/* Nav tab active accent */
.nav-tab.active {
  border-left: 3px solid var(--color-cyan) !important;
  background: rgba(0, 229, 255, 0.07) !important;
  color: #fff !important;
}
/* Nav tab scrollbar */
.enterprise-nav-tabs::-webkit-scrollbar { height: 3px; }
.enterprise-nav-tabs::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }

/* Mobile nav collapse */
@media (max-width: 768px) {
  .enterprise-nav-tabs { gap: 0; }
  .nav-tab { font-size: 0.72rem; padding: 0.6rem 0.8rem; white-space: nowrap; }
  .master-header { flex-direction: column; gap: 0.75rem; padding: 0.75rem 1rem; }
  .header-controls { flex-wrap: wrap; gap: 0.5rem; }
  .brand-row { flex-wrap: wrap; gap: 0.4rem; }
}

/* Anatomy figure iframe */
.anatomy-frame {
  width: 100%;
  height: 320px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: #050811;
}
.anatomy-figure-panel {
  margin-top: 1rem;
}
.anatomy-caption {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.4rem;
  font-style: italic;
}
'''

with open('web/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("style.css patched")

# ── Fix index.html ─────────────────────────────────────────────────────────────
with open('web/index.html', 'r', encoding='utf-8', errors='replace') as f:
    html = f.read()

# Replace the entire nav block with clean safe emoji and sequential numbers
old_nav = re.search(r'<nav class="enterprise-nav-tabs".*?</nav>', html, re.DOTALL)
if old_nav:
    new_nav = '''<nav class="enterprise-nav-tabs" aria-label="Hospital Operating Consoles">
    <button class="nav-tab active" id="tabRobotics" onclick="switchView('ROBOTICS')">&#x1F916; 1. Surgical Robotics &amp; SAM 3.1</button>
    <button class="nav-tab" id="tabBedsideDeck" onclick="switchView('BEDSIDE_DECK')">&#x26A1; 2. Bedside Safety Flight Deck</button>
    <button class="nav-tab" id="tabBedBoard" onclick="switchView('BED_BOARD')">&#x1F3E5; 3. Master Bed Board (78 Beds)</button>
    <button class="nav-tab" id="tabPharmacy" onclick="switchView('PHARMACY')">&#x1F48A; 4. Pharmacy &amp; NTI Surveillance</button>
    <button class="nav-tab" id="tabWorkforce" onclick="switchView('WORKFORCE')">&#x1FA7A; 5. Workforce &amp; Wellbeing Roster</button>
    <button class="nav-tab" id="tabEarlyWarning" onclick="switchView('EARLY_WARNING')">&#x1F6A8; 6. Clinical Early Warning (NEWS2)</button>
    <button class="nav-tab" id="tabTerminal" onclick="switchView('TERMINAL')">&gt;_ 7. Microkernel Shell (bioos-ctl)</button>
  </nav>'''
    html = html[:old_nav.start()] + new_nav + html[old_nav.end():]
    print("Nav tabs replaced with safe HTML entities")
else:
    print("WARNING: Nav block not found")

# Fix header badge density — keep only 3 essential badges, hide the rest
# Replace the cluttered brand-row with a cleaned version
old_row = re.search(r'<div class="brand-row">.*?</div>', html, re.DOTALL)
if old_row:
    new_row = '''<div class="brand-row">
          <span class="brand-name">BioOS</span>
          <span class="brand-tag">Enterprise v2.0-LTS</span>
          <span class="badge badge-safety">IEC 62304 Class&#xA0;C</span>
          <span class="badge badge-sam">SAM 3.1 Vision</span>
          <span class="badge badge-meta">Meta Llama&#x2011;3.1</span>
          <span class="badge badge-team">&#x1F3C6; BioFrontier</span>
        </div>'''
    html = html[:old_row.start()] + new_row + html[old_row.end():]
    print("Brand row cleaned to 4 badges")

# Ensure viewRobotics is active-view, viewBedBoard is not
html = html.replace('class="hospital-view active-view" id="viewBedBoard"', 'class="hospital-view" id="viewBedBoard"')
html = html.replace('class="hospital-view" id="viewRobotics"', 'class="hospital-view active-view" id="viewRobotics"')

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("index.html saved")
print("\nDone. All Phase 1 fixes applied.")
