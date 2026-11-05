import re

with open('web/index.html', 'r', encoding='utf-8', errors='replace') as f:
    html = f.read()

fig2_panel = """
    <!-- Anatomy Fig 2: Plane A SSR Virtual Fixture Trip -->
    <div class="anatomy-figure-panel" style="margin-top:1.5rem;">
      <div class="card-title-row" style="margin-bottom:0.5rem;">
        <span class="card-title">Fig&nbsp;2 &mdash; Plane&nbsp;A SSR Virtual Fixture Bench Rig &mdash; &lt;2&nbsp;ms Emergency Lockout (Isometric Figure)</span>
        <a href="figures/ssr-trip/ssr-trip.html" target="_blank" class="badge badge-safety" style="text-decoration:none;cursor:pointer;">Open Full Figure</a>
      </div>
      <iframe src="figures/ssr-trip/ssr-trip.html"
              title="Plane A SSR Virtual Fixture Trip"
              scrolling="no"
              style="width:100%;height:380px;border:1px solid #1e293b;border-radius:8px;background:#050811;"></iframe>
      <p style="font-size:0.75rem;color:#94a3b8;margin-top:0.4rem;font-style:italic;">
        When Meta SAM&nbsp;3.1 detects the robotic instrument within 0.80&nbsp;mm of the hepatic artery, Plane&nbsp;A fires this solid-state relay, cutting motor power in &lt;2&nbsp;ms &mdash; 10&times; faster than any mechanical relay. The LVDT ruler shows the live distance margin; the red dashed line is the lockout threshold.
      </p>
    </div>
"""

# Insert after the Fig 1 anatomy panel (find the second anatomy-figure-panel insertion point = after Fig 1 iframe p tag)
# We'll insert before the section closing tag of viewRobotics
m = re.search(r'(</section>)\s*\n\s*(<!--\s*128-Byte)', html)
if m:
    pos = m.start(1)
    html = html[:pos] + fig2_panel + '\n  ' + html[pos:]
    print("Fig 2 panel inserted")
else:
    # Find end of fig1 panel and insert after it
    fig1_end = html.rfind('</div>\n    </div>\n  </section>')
    if fig1_end != -1:
        insert = fig1_end + len('</div>')
        html = html[:insert] + fig2_panel + html[insert:]
        print("Fig 2 inserted (fallback)")
    else:
        # Last resort: insert before AMSV footer
        footer_m = re.search(r'<!--\s*128-Byte Tri-Plane', html)
        if footer_m:
            html = html[:footer_m.start()] + fig2_panel + '\n  ' + html[footer_m.start():]
            print("Fig 2 inserted (last resort)")
        else:
            print("ERROR: Could not find insertion point")

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Done.")
