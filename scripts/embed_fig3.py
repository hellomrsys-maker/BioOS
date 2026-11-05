import re

with open('web/index.html', 'r', encoding='utf-8', errors='replace') as f:
    html = f.read()

fig3_panel = """
    <!-- Anatomy Fig 3: Meta SAM 3.1 Margin Dial-Indicator -->
    <div class="anatomy-figure-panel" style="margin-top:1.5rem;">
      <div class="card-title-row" style="margin-bottom:0.5rem;">
        <span class="card-title">Fig&nbsp;3 &mdash; Meta SAM 3.1 Margin Dial-Indicator Gauge &mdash; Critical Distance Telemetry (Isometric Figure)</span>
        <a href="figures/sam-dial/sam-dial.html" target="_blank" class="badge badge-sam" style="text-decoration:none;cursor:pointer;">Open Full Figure</a>
      </div>
      <iframe src="figures/sam-dial/sam-dial.html"
              title="Meta SAM 3.1 Margin Dial-Indicator"
              scrolling="no"
              style="width:100%;height:380px;border:1px solid #1e293b;border-radius:8px;background:#050811;"></iframe>
      <p style="font-size:0.75rem;color:#94a3b8;margin-top:0.4rem;font-style:italic;">
        Physical dial-indicator analogue of Meta SAM&nbsp;3.1 vision inference: the gauge translates high-dimensional neural segmentation masks into an exact geometric Euclidean distance. The cyan needle reads 1.42&nbsp;mm; entering the red sector (&lt;0.80&nbsp;mm) triggers the Plane&nbsp;A emergency interlock.
      </p>
    </div>
"""

# Insert before the closing </section> of viewRobotics
m = re.search(r'(</section>)\s*\n\s*(<!--\s*128-Byte)', html)
if m:
    pos = m.start(1)
    html = html[:pos] + fig3_panel + '\n  ' + html[pos:]
    print("Fig 3 panel inserted before footer")
else:
    footer_m = re.search(r'<!--\s*128-Byte Tri-Plane', html)
    if footer_m:
        html = html[:footer_m.start()] + fig3_panel + '\n  ' + html[footer_m.start():]
        print("Fig 3 inserted before footer marker")
    else:
        print("ERROR: Insertion target not found")

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Done embedding Fig 3.")
