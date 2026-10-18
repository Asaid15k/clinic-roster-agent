"""Look and feel. One hook restyles every page the app returns, so no template has to change.
- Agent pages (/agent, /tests ...): dark dashboard theme + top navigation + 'agent is working' overlay
- Public pages (/cms, /portal): light, clean clinic-website theme with time chips
Internal requests made by the agent itself (Flask test client) are left untouched, so verification reads the raw page."""
from flask import request

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
META = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'

NAV = """<div class="nav"><a class="brand" href="/">&#129657; Roster Agent</a>
<span><a href="/agent">New input</a><a href="/agent/dashboard">Dashboard</a><a href="/tests">Test runs</a><a href="/cms?fresh=1" target="_blank">Public site</a><a href="/portal" target="_blank">Portal</a></span></div>"""

BANNER = '<div class="banner"><b>Sunrise Clinic</b>{sub}</div>'

ADMIN_CSS = """<style>
:root{--bg:#0a0e1f;--card:#121832;--line:#26305a;--text:#e8ebf7;--mut:#8f98c0;--a:#7c5cff;--b:#22d3ee;--ok:#34d399;--bad:#fb7185;--warn:#fbbf24}
html{background:var(--bg)}
body{font-family:Inter,system-ui,"Segoe UI",sans-serif!important;color:var(--text);max-width:1100px!important;margin:0 auto!important;padding:92px 22px 70px;min-height:100vh;
background:radial-gradient(900px 420px at 8% -8%,#2d217a66,transparent),radial-gradient(800px 420px at 100% 0,#0e749055,transparent)}
.nav{position:fixed;top:0;left:0;right:0;z-index:50;display:flex;justify-content:space-between;align-items:center;padding:13px 28px;background:#0a0e1fcc;backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.nav a{color:var(--mut);text-decoration:none;margin-left:20px;font-size:14px;font-weight:500;transition:.15s}.nav a:hover{color:#fff}
.nav .brand{color:#fff;font-weight:800;font-size:17px;margin:0}
a{color:var(--b)}
h1{font-size:54px;line-height:1.05;margin:10px 0 14px;font-weight:800;background:linear-gradient(90deg,#fff,#a5b4fc 55%,#67e8f9);-webkit-background-clip:text;background-clip:text;color:transparent}
h2{font-size:30px;font-weight:800;margin:6px 0 14px;background:linear-gradient(90deg,#fff,#a5b4fc 60%,#67e8f9);-webkit-background-clip:text;background-clip:text;color:transparent}
h3{color:#c7d2fe;margin:26px 0 8px}
p{color:#c3c9e6;line-height:1.55}i{color:#fff}
table{border-collapse:separate!important;border-spacing:0;width:100%;background:var(--card);border:1px solid var(--line)!important;border-radius:14px;overflow:hidden;margin:14px 0}
th{background:#171f40;color:#aab4e6;text-transform:uppercase;font-size:11px!important;letter-spacing:.08em;text-align:left}
td,th{border:0!important;border-bottom:1px solid var(--line)!important;padding:11px 14px!important;font-size:14px!important;color:var(--text)}
tr:last-child td{border-bottom:0!important}tr:hover td{background:#161d3d}
.ok{color:var(--ok)!important}.bad{color:var(--bad)!important}.warn{color:var(--warn)!important}
b.ok,b.bad,b.warn,span.ok,span.bad,span.warn{padding:2px 11px;border-radius:999px;font-size:13px}
b.ok{background:#34d39926}b.bad{background:#fb718526}b.warn{background:#fbbf2426}
button{background:linear-gradient(135deg,var(--a),#3b82f6 60%,var(--b))!important;color:#fff!important;border:0!important;border-radius:11px!important;padding:11px 20px!important;font-weight:700;font-size:14px;cursor:pointer;box-shadow:0 6px 22px #7c5cff44;transition:.15s}
button:hover{transform:translateY(-2px);box-shadow:0 12px 28px #22d3ee44}
form[action*="reject"] button{background:#252c52!important;box-shadow:none}
textarea{width:100%;box-sizing:border-box;background:#0d1330;color:#fff;border:1px solid var(--line);border-radius:12px;padding:14px;font:16px Inter,system-ui,sans-serif;outline:0;transition:.15s}
textarea:focus{border-color:var(--a);box-shadow:0 0 0 4px #7c5cff33}
pre{background:#0b1026;border:1px solid var(--line);border-radius:10px;padding:10px;color:#b6c2ff!important;font-size:12px!important;margin:0}
div[style*="border"]{border:1px solid #2b3358!important;background:var(--card);border-radius:14px!important;padding:16px 18px!important;margin:12px 0!important;line-height:1.6}
ul{color:#fda4af}
.hero{padding:30px 0 10px}.tag{display:inline-block;padding:5px 14px;border-radius:999px;border:1px solid var(--line);background:#ffffff0d;color:#a5b4fc;font-size:13px;font-weight:600}
.hero p{font-size:19px;max-width:660px}
.cta{display:inline-block;margin:10px 12px 0 0;padding:13px 24px;border-radius:12px;background:linear-gradient(135deg,var(--a),#3b82f6 60%,var(--b));color:#fff;text-decoration:none;font-weight:700;box-shadow:0 8px 26px #7c5cff55;transition:.15s}
.cta:hover{transform:translateY(-2px)}.cta.ghost{background:transparent;border:1px solid var(--line);box-shadow:none;color:#fff}
.flow{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:38px 0 26px}
.flow div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;font-size:12px;color:var(--mut);text-align:center}
.flow b{display:block;color:#fff;font-size:15px;margin-top:6px}.flow span{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:50%;background:linear-gradient(135deg,var(--a),var(--b));color:#fff;font-weight:700}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}
.cards a{display:block;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;text-decoration:none;color:var(--mut);transition:.15s}
.cards a:hover{transform:translateY(-4px);border-color:var(--a)}.cards b{display:block;color:#fff;font-size:17px;margin-bottom:6px}
.ov{position:fixed;inset:0;z-index:99;background:#070a17e6;backdrop-filter:blur(6px);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;color:#fff;font-size:20px;font-weight:700}
.ov small{color:var(--mut);font-weight:400;font-size:14px}.sp{width:54px;height:54px;border-radius:50%;border:5px solid #26305a;border-top-color:var(--b);animation:sp .8s linear infinite;margin-bottom:12px}
@keyframes sp{to{transform:rotate(360deg)}}
@media(max-width:760px){.flow{grid-template-columns:repeat(2,1fr)}h1{font-size:38px}.nav span a:nth-child(n+4){display:none}}
</style>"""

ADMIN_JS = """<script>document.addEventListener("submit",function(e){var b=e.target.querySelector("button"),o=document.createElement("div");
o.className="ov";o.innerHTML='<div class="sp"></div>'+(b?b.textContent:"Working")+'&hellip;<small>The agent is working. Please wait.</small>';document.body.appendChild(o)});</script>"""

PUBLIC_CSS = """<style>
html{background:#f3fbf9}
body{font-family:Inter,system-ui,"Segoe UI",sans-serif!important;color:#134e4a;max-width:780px!important;margin:0 auto!important;padding:0 20px 60px!important}
.banner{margin:0 -20px 26px;padding:34px 30px 30px;background:linear-gradient(120deg,#0f766e,#14b8a6 62%,#5eead4);color:#fff;border-radius:0 0 28px 28px;box-shadow:0 10px 30px #0f766e33}
.banner b{display:block;font-size:30px;font-weight:800}.banner span{opacity:.9;font-size:15px}
h2{color:#0f766e;font-size:24px;margin:0 0 4px}h3{color:#115e59;margin:30px 0 8px;font-size:18px}
table{border:0!important;width:100%;border-collapse:separate!important;border-spacing:0;background:#fff;border-radius:16px;box-shadow:0 6px 24px #0f766e14;overflow:hidden}
td{border:0!important;border-bottom:1px solid #e3f3ef!important;padding:11px 16px!important;font-size:14px}
tr:last-child td{border-bottom:0!important}td:first-child{font-weight:700;width:130px;color:#134e4a;background:#f7fcfb}
.chip{display:inline-block;padding:4px 12px;margin:2px 6px 2px 0;border-radius:999px;background:#ccfbf1;color:#0f766e;font-size:13px;font-weight:700}
.chip.none{background:#fee2e2;color:#b91c1c}small{color:#5b8a86;font-size:12px}
</style>"""

PUBLIC_JS = """<script>document.querySelectorAll("table tr").forEach(function(tr){var td=tr.children[1];if(!td)return;var t=td.textContent.trim();
td.innerHTML=t==="No availability"?'<span class="chip none">No availability</span>':t.split(",").map(function(s){return '<span class="chip">'+s.trim()+'</span>'}).join("")});</script>"""

HOME = """<div class="hero"><span class="tag">Agentic AI &middot; Ziro Hackathon 2026</span>
<h1>Clinic Roster Agent</h1>
<p>Update a doctor's availability once. The agent finds booking conflicts, asks for your approval, publishes to the website and the booking portal, then proves it worked.</p>
<a class="cta" href="/agent">Start a roster change</a><a class="cta ghost" href="/tests">Run the 4 test cases</a></div>
<div class="flow"><div><span>1</span><b>Collect</b>roster message</div><div><span>2</span><b>Plan</b>find conflicts</div><div><span>3</span><b>Find</b>CMS + bookings</div>
<div><span>4</span><b>Approve</b>human check</div><div><span>5</span><b>Act</b>update both</div><div><span>6</span><b>Verify</b>reload public pages</div></div>
<div class="cards"><a href="/agent"><b>New roster change</b>Type a leave message in plain English</a>
<a href="/agent/dashboard"><b>Dashboard</b>Every input and unresolved items</a>
<a href="/tests"><b>Official test runs</b>TC1 to TC4 with evidence</a>
<a href="/cms?fresh=1" target="_blank"><b>Public website</b>What patients see</a>
<a href="/portal" target="_blank"><b>Booking portal</b>Where slots are booked</a></div>"""


def install(app):
    @app.after_request
    def restyle(resp):
        if (resp.mimetype != "text/html" or resp.status_code >= 300 or resp.direct_passthrough
                or "Werkzeug" in request.headers.get("User-Agent", "")):
            return resp
        body = resp.get_data(as_text=True)
        if request.path in ("/cms", "/portal"):
            sub = "<span>Doctor availability</span>" if request.path == "/cms" else "<span>Book an appointment</span>"
            out = META + FONTS + PUBLIC_CSS + BANNER.format(sub=sub) + body + PUBLIC_JS
        else:
            out = META + FONTS + NAV + body + ADMIN_CSS + ADMIN_JS
        resp.set_data(out)
        return resp