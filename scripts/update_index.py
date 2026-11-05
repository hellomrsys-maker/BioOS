import re

with open('web/index.html', 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

# Make Robotics tab first and active
tab_pattern = re.compile(r'<nav class="enterprise-nav-tabs".*?</nav>', re.DOTALL)
new_tabs = '''<nav class="enterprise-nav-tabs" aria-label="Hospital Operating Consoles">
    <button class="nav-tab active" id="tabRobotics" onclick="switchView('ROBOTICS')">🤖 1. Surgical Robotics &amp; SAM 3.1</button>
    <button class="nav-tab" id="tabBedsideDeck" onclick="switchView('BEDSIDE_DECK')">⚡ 2. Bedside Safety Flight Deck</button>
    <button class="nav-tab" id="tabBedBoard" onclick="switchView('BED_BOARD')">🏥 3. Master Bed Board (78 Beds)</button>
    <button class="nav-tab" id="tabPharmacy" onclick="switchView('PHARMACY')">💊 4. Pharmacy &amp; NTI Surveillance</button>
    <button class="nav-tab" id="tabWorkforce" onclick="switchView('WORKFORCE')">🩺 5. Workforce &amp; Wellbeing Roster</button>
    <button class="nav-tab" id="tabEarlyWarning" onclick="switchView('EARLY_WARNING')">🚨 6. Clinical Early Warning (NEWS2)</button>
    <button class="nav-tab" id="tabTerminal" onclick="switchView('TERMINAL')">&gt;_ 7. Microkernel Shell (bioos-ctl)</button>
  </nav>'''

text = tab_pattern.sub(new_tabs, text, count=1)

# Set viewRobotics as active section, unset viewBedBoard
text = text.replace('class="hospital-view active-view" id="viewBedBoard"', 'class="hospital-view" id="viewBedBoard"')
text = text.replace('class="hospital-view" id="viewRobotics"', 'class="hospital-view active-view" id="viewRobotics"')

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated web/index.html successfully")
