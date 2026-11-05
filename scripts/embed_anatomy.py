import re

with open('web/index.html', 'r', encoding='utf-8', errors='replace') as f:
    html = f.read()

anatomy_panel = """
    <!-- Anatomy Fig 1: AMSV Tri-Plane Card-Cage -->
    <div class="anatomy-figure-panel" style="margin-top:1.5rem;">
      <div class="card-title-row" style="margin-bottom:0.5rem;">
        <span class="card-title">Fig&nbsp;1 &mdash; 128-byte Tri-Plane AMSV Zero-Bridge Memory Architecture (Isometric Figure)</span>
        <a href="figures/amsv-cage/amsv-cage.html" target="_blank" class="badge badge-meta" style="text-decoration:none;cursor:pointer;">Open Full Figure</a>
      </div>
      <iframe src="figures/amsv-cage/amsv-cage.html"
              title="Tri-Plane AMSV Memory Architecture"
              scrolling="no"
              style="width:100%;height:380px;border:1px solid #1e293b;border-radius:8px;background:#050811;"></iframe>
      <p style="font-size:0.75rem;color:#94a3b8;margin-top:0.4rem;font-style:italic;">
        Three PCB cards (Plane&nbsp;A Rust 1000&nbsp;Hz kernel, Plane&nbsp;C Kalman 100&nbsp;Hz observer, Plane&nbsp;B Meta Llama-3.1) share one 128-byte backplane bus at address 0x00007FFE2C7600C0. Zero serialisation. Zero bridge. Zero nanoseconds of synchronisation latency.
      </p>
    </div>
"""

# Find the closing tag of viewRobotics section
m = re.search(r'(</section>)\s*\n\s*(<!--\s*128-Byte)', html)
if m:
    insert_pos = m.start(1)
    html = html[:insert_pos] + anatomy_panel + '\n  ' + html[insert_pos:]
    print("Anatomy panel inserted before footer")
else:
    # fallback: insert before footer
    m2 = re.search(r'(</section>)\s*\n\s*(<!--\s*128)', html)
    if m2:
        insert_pos = m2.start(1)
        html = html[:insert_pos] + anatomy_panel + '\n  ' + html[insert_pos:]
        print("Anatomy panel inserted (fallback)")
    else:
        # Last resort: find viewRobotics section end
        m3 = re.search(r'id="viewRobotics"', html)
        if m3:
            # Find the section close after it
            sec_end = html.find('</section>', m3.start())
            if sec_end != -1:
                html = html[:sec_end] + anatomy_panel + '\n  ' + html[sec_end:]
                print("Anatomy panel inserted (last resort)")
        else:
            print("ERROR: Could not find insertion point")

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Done.")
