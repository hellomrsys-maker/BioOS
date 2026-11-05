import re

with open('web/index.html', 'r', encoding='utf-8', errors='replace') as f:
    html = f.read()

fig4_panel = """
    <!-- Anatomy Fig 4: Plane C Kalman EKF Ripple Tank -->
    <div class="anatomy-figure-panel" style="margin-top:1.5rem;">
      <div class="card-title-row" style="margin-bottom:0.5rem;">
        <span class="card-title">Fig&nbsp;4 &mdash; Plane&nbsp;C Kalman Observer &mdash; Physiological Wave Ripple Tank (Isometric Figure)</span>
        <a href="figures/kalman-tank/kalman-tank.html" target="_blank" class="badge badge-ice" style="text-decoration:none;cursor:pointer;">Open Full Figure</a>
      </div>
      <iframe src="figures/kalman-tank/kalman-tank.html"
              title="Plane C Kalman Observer Ripple Tank"
              scrolling="no"
              style="width:100%;height:380px;border:1px solid #1e293b;border-radius:8px;background:#050811;"></iframe>
      <p style="font-size:0.75rem;color:#94a3b8;margin-top:0.4rem;font-style:italic;">
        Physical ripple-tank analogue of Plane&nbsp;C 100&nbsp;Hz Extended Kalman Filter (EKF): twin synchronized dippers model high-frequency cardiac pulses (75&nbsp;bpm) and low-frequency respiratory motion (15&nbsp;bpm). The strobe observer reconstructs organ phase and projects the Airbus-style Alpha-Floor hemodynamic safety corridor (&lt;55&nbsp;mmHg automatic infusion clamp) onto the lower deck.
      </p>
    </div>
"""

# Insert before the closing </section> of viewRobotics
m = re.search(r'(</section>)\s*\n\s*(<!--\s*128-Byte)', html)
if m:
    pos = m.start(1)
    html = html[:pos] + fig4_panel + '\n  ' + html[pos:]
    print("Fig 4 panel inserted before footer")
else:
    footer_m = re.search(r'<!--\s*128-Byte Tri-Plane', html)
    if footer_m:
        html = html[:footer_m.start()] + fig4_panel + '\n  ' + html[footer_m.start():]
        print("Fig 4 inserted before footer marker")
    else:
        print("ERROR: Insertion target not found")

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Done embedding Fig 4.")
