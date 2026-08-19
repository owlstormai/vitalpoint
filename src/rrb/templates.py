"""Presentation layer: HTML/CSS rendering for the web views.

Kept separate from web.py so routes stay about data and this stays about
design. Renders from the structured Brief object rather than its markdown
serialization, so each claim can sit beside the evidence that supports it.

Aesthetic: modern clinical SaaS — layered cool neutrals, a calm teal primary,
soft elevation, generous spacing, and card-based data. Webfonts are
progressive enhancement; the fallback stacks keep the app fully usable with no
network, matching the project's offline-first ethos.
"""
import html

FONTS = ("https://fonts.googleapis.com/css2?"
         "family=Manrope:wght@600;700;800"
         "&family=Plus+Jakarta+Sans:wght@400;500;600;700"
         "&family=IBM+Plex+Mono:wght@400;500&display=swap")

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  /* No pure white anywhere: paper-toned off-whites cut the glare of a bright
     screen while keeping enough separation between page, card and sunk. */
  --bg:#e7edeb; --surface:#f5f9f8; --surface-2:#eef4f2; --sunk:#e0e9e6;
  /* --ink-3 carries real content (column headers, citation metadata, dates),
     so it is set to clear 4.5:1 on every surface above, not just on cards. */
  --ink:#0d1f1d; --ink-2:#465b58; --ink-3:#556764;
  --line:#d9e4e1; --line-2:#c2d1cd;
  --teal:#0d6e66; --teal-2:#12958a; --teal-bg:#e4f2f0; --on-teal:#ffffff;
  --high:#b03a30; --high-bg:#fbeae8; --high-line:#f0cdc8;
  --med:#8a590c; --med-bg:#fcf1de; --low:#127a5c; --low-bg:#e2f3ec;
  --shadow:0 1px 2px rgba(13,31,29,.05),0 8px 24px -12px rgba(13,31,29,.14);
  --shadow-lg:0 2px 4px rgba(13,31,29,.05),0 18px 44px -20px rgba(13,31,29,.24);
  --r:14px; --r-sm:9px;
  --display:"Manrope",-apple-system,"Segoe UI",sans-serif;
  --sans:"Plus Jakarta Sans",-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#0a1413; --surface:#101d1b; --surface-2:#152321; --sunk:#1b2a28;
    --ink:#e9f2f0; --ink-2:#a3b6b3; --ink-3:#849794;
    --line:#1e2f2d; --line-2:#2a3d3a;
    --teal:#3ec7b6; --teal-2:#5bdccb; --teal-bg:#12312d; --on-teal:#062120;
    --high:#f08472; --high-bg:#2e1512; --high-line:#4a221c;
    --med:#e0aa4e; --med-bg:#2c2010; --low:#4fc79b; --low-bg:#0f2d23;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -12px rgba(0,0,0,.6);
    --shadow-lg:0 2px 4px rgba(0,0,0,.4),0 18px 44px -20px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --bg:#0a1413; --surface:#101d1b; --surface-2:#152321; --sunk:#1b2a28;
  --ink:#e9f2f0; --ink-2:#a3b6b3; --ink-3:#849794;
  --line:#1e2f2d; --line-2:#2a3d3a;
  --teal:#3ec7b6; --teal-2:#5bdccb; --teal-bg:#12312d; --on-teal:#062120;
  --high:#f08472; --high-bg:#2e1512; --high-line:#4a221c;
  --med:#e0aa4e; --med-bg:#2c2010; --low:#4fc79b; --low-bg:#0f2d23;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -12px rgba(0,0,0,.6);
  --shadow-lg:0 2px 4px rgba(0,0,0,.4),0 18px 44px -20px rgba(0,0,0,.7);
}
html{-webkit-text-size-adjust:100%}
/* one focus treatment for every interactive element, so keyboard users get
   the same affordance the selects already had */
:where(a,button,select,[tabindex]):focus-visible{
  outline:2px solid var(--teal);outline-offset:2px;border-radius:4px;
}
body{
  margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased;
  font-feature-settings:"tnum" 1,"cv05" 1;
}
.wrap{max-width:1240px;margin:0 auto;padding:0 26px 90px}
.brief-wrap{max-width:1000px}
a{color:inherit}
/* ---------- top bar ---------- */
.topbar{
  position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 82%,transparent);
  backdrop-filter:saturate(1.4) blur(12px);border-bottom:1px solid var(--line);
  margin-bottom:30px;
}
.topbar .inner{
  max-width:1240px;margin:0 auto;padding:13px 26px;display:flex;
  align-items:center;gap:14px;
}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none}
.logo{
  width:30px;height:30px;border-radius:9px;background:var(--teal);
  /* --teal is deliberately light in dark mode, so the glyph rides a token
     that flips with it rather than a hardcoded white that would disappear */
  color:var(--on-teal);
  display:grid;place-items:center;flex:none;
  box-shadow:0 2px 8px -2px color-mix(in srgb,var(--teal) 60%,transparent);
}
.wordmark{font-family:var(--display);font-weight:800;font-size:16px;
  letter-spacing:-.02em}
.wordmark span{color:var(--teal)}
.spacer{flex:1}
.asof{font-family:var(--mono);font-size:11px;color:var(--ink-3);
  letter-spacing:.02em}
.theme-btn{
  display:inline-flex;align-items:center;gap:7px;height:32px;padding:0 11px;
  border-radius:8px;border:1px solid var(--line-2);background:var(--surface);
  color:var(--ink-2);cursor:pointer;font-family:var(--sans);font-size:12.5px;
  font-weight:600;transition:color .16s,border-color .16s,transform .16s;
}
.theme-btn:hover{color:var(--teal);border-color:var(--teal);
  transform:translateY(-1px)}
.theme-btn svg{flex:none}
/* The button advertises the mode it switches TO, so its icon and label must
   track the resolved theme. Doing the swap in CSS rather than JS keeps it
   correct on first paint with no flash of the wrong label. */
.t-sun,.t-light{display:none}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]) .t-sun,
  :root:not([data-theme="light"]) .t-light{display:inline-flex}
  :root:not([data-theme="light"]) .t-moon,
  :root:not([data-theme="light"]) .t-dark{display:none}
}
:root[data-theme="dark"] .t-sun,
:root[data-theme="dark"] .t-light{display:inline-flex}
:root[data-theme="dark"] .t-moon,
:root[data-theme="dark"] .t-dark{display:none}
/* ---------- page head ---------- */
.pagehead{margin-bottom:24px}
.pagehead h1{
  font-family:var(--display);font-weight:800;font-size:clamp(26px,4vw,38px);
  letter-spacing:-.032em;line-height:1.08;margin:0 0 6px;
}
.pagehead p{margin:0;color:var(--ink-2);font-size:15px;max-width:62ch}
/* ---------- kpi cards ---------- */
.kpis{display:grid;gap:14px;margin-bottom:22px;
  grid-template-columns:repeat(auto-fit,minmax(212px,1fr))}
.kpi{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
  padding:18px 20px;box-shadow:var(--shadow);position:relative;overflow:hidden;
  transition:transform .18s,box-shadow .18s;
}
.kpi:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.kpi::after{content:"";position:absolute;inset:0 auto 0 0;width:3px;
  background:var(--teal)}
.kpi.risk::after{background:var(--high)}
.kpi .k{font-size:12px;font-weight:600;letter-spacing:.02em;color:var(--ink-3);
  text-transform:uppercase;margin-bottom:10px}
.kpi .v{font-family:var(--display);font-weight:800;font-size:34px;
  line-height:1;letter-spacing:-.03em}
.kpi.risk .v{color:var(--high)}
.kpi .sub{font-size:12.5px;color:var(--ink-3);margin-top:7px}
/* ---------- card ---------- */
.card{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
  box-shadow:var(--shadow);
}
.card-head{padding:16px 20px;border-bottom:1px solid var(--line);
  display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.card-head h2{font-family:var(--display);font-weight:700;font-size:15px;
  letter-spacing:-.015em;margin:0}
.card-body{padding:20px}
/* ---------- filters ---------- */
.filters{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;
  padding:16px 20px}
.field{display:flex;flex-direction:column;gap:6px}
.field label{font-size:11.5px;font-weight:600;letter-spacing:.03em;
  text-transform:uppercase;color:var(--ink-3)}
select{
  font-family:var(--sans);font-size:13.5px;font-weight:500;color:var(--ink);
  background:var(--surface-2);border:1px solid var(--line-2);
  border-radius:var(--r-sm);padding:8px 11px;min-width:152px;cursor:pointer;
  transition:border-color .16s,box-shadow .16s;appearance:none;
  background-image:linear-gradient(45deg,transparent 50%,currentColor 50%),
    linear-gradient(135deg,currentColor 50%,transparent 50%);
  background-position:calc(100% - 15px) 55%,calc(100% - 10px) 55%;
  background-size:5px 5px,5px 5px;background-repeat:no-repeat;padding-right:30px;
}
select:hover{border-color:var(--line-2)}
select:focus{outline:none;border-color:var(--teal);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--teal) 18%,transparent)}
.btn{
  font-family:var(--sans);font-size:13.5px;font-weight:600;padding:9px 18px;
  border-radius:var(--r-sm);cursor:pointer;border:1px solid var(--teal);
  background:var(--teal);color:var(--on-teal);
  transition:filter .16s,transform .16s;
  text-decoration:none;display:inline-block;
}
.btn:hover{filter:brightness(1.08);transform:translateY(-1px)}
.btn.ghost{background:var(--surface-2);color:var(--ink-2);
  border-color:var(--line-2)}
.btn.ghost:hover{color:var(--teal);border-color:var(--teal)}
.count{margin-left:auto;font-size:13px;color:var(--ink-3);padding-bottom:10px}
.count b{color:var(--ink);font-weight:600}
/* ---------- table ---------- */
.scroll{overflow-x:auto;border-radius:0 0 var(--r) var(--r)}
table{width:100%;border-collapse:collapse}
th{
  font-size:11.5px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;
  color:var(--ink-3);text-align:left;padding:12px 16px;background:var(--surface-2);
  border-bottom:1px solid var(--line);white-space:nowrap;position:sticky;top:57px;
}
th.num,td.num{text-align:right}
td{padding:13px 16px;border-bottom:1px solid var(--line);vertical-align:middle}
tbody tr{transition:background .14s}
tbody tr:hover{background:var(--surface-2)}
tbody tr:last-child td{border-bottom:0}
.aid{font-family:var(--mono);font-size:12px;color:var(--ink-3);
  text-decoration:none}
.practice{font-weight:600;font-size:14.5px;text-decoration:none;
  display:inline-block}
tbody tr:hover .practice{color:var(--teal)}
.place{font-size:12.5px;color:var(--ink-3);margin-top:1px}
.mono{font-family:var(--mono);font-size:12.5px}
.badge{
  display:inline-flex;align-items:center;gap:6px;font-size:11.5px;
  font-weight:600;padding:4px 11px 4px 8px;border-radius:999px;
  white-space:nowrap;text-transform:capitalize;
}
.badge::before{content:"";width:6px;height:6px;border-radius:50%;
  background:currentColor}
.badge.high{color:var(--high);background:var(--high-bg)}
.badge.medium{color:var(--med);background:var(--med-bg)}
.badge.low{color:var(--low);background:var(--low-bg)}
.trend{display:flex;align-items:center;gap:9px}
.delta{font-family:var(--mono);font-size:12px;color:var(--ink-3)}
.delta.down{color:var(--high)}
.sat{display:flex;align-items:center;gap:9px}
.satbar{width:46px;height:5px;background:var(--sunk);border-radius:999px;
  overflow:hidden;flex:none}
.satbar i{display:block;height:100%;border-radius:999px}
.soon{font-family:var(--mono);font-size:12px;padding:2px 8px;border-radius:999px;
  background:var(--sunk);color:var(--ink-2)}
.soon.urgent{background:var(--high-bg);color:var(--high);font-weight:500}
.empty{padding:64px 20px;text-align:center;color:var(--ink-3)}
.empty strong{display:block;font-family:var(--display);font-size:19px;
  color:var(--ink);margin-bottom:6px}
/* ---------- brief ---------- */
.backlink{display:inline-flex;align-items:center;gap:7px;font-size:13.5px;
  font-weight:600;color:var(--ink-2);text-decoration:none;margin-bottom:16px}
.backlink:hover{color:var(--teal)}
.hero{padding:26px 28px;margin-bottom:16px}
.eyebrow{display:inline-flex;align-items:center;gap:7px;font-size:11.5px;
  font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  color:var(--teal);background:var(--teal-bg);padding:5px 11px;
  border-radius:999px;margin-bottom:14px}
.hero h1{font-family:var(--display);font-weight:800;
  font-size:clamp(26px,4.4vw,40px);letter-spacing:-.032em;line-height:1.06;
  margin:0 0 14px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{font-size:12.5px;color:var(--ink-2);background:var(--surface-2);
  border:1px solid var(--line);padding:5px 11px;border-radius:999px}
.chip b{color:var(--ink);font-weight:600}
.verdict{display:flex;align-items:center;gap:26px;flex-wrap:wrap;
  padding:24px 28px;margin-bottom:16px;border-left:4px solid var(--line-2)}
.verdict.high{border-left-color:var(--high)}
.verdict.medium{border-left-color:var(--med)}
.verdict.low{border-left-color:var(--low)}
.verdict .lvl{font-family:var(--display);font-weight:800;
  font-size:clamp(30px,5.6vw,46px);line-height:1;letter-spacing:-.035em}
.verdict.high .lvl{color:var(--high)}
.verdict.medium .lvl{color:var(--med)}
.verdict.low .lvl{color:var(--low)}
.verdict .meta{font-size:13px;color:var(--ink-3);margin-top:4px}
.meter{flex:1 1 200px;min-width:160px;height:7px;background:var(--sunk);
  border-radius:999px;overflow:hidden}
.meter i{display:block;height:100%;border-radius:999px}
section{margin-bottom:16px}
.driver{padding:18px 20px;border-bottom:1px solid var(--line)}
.driver:last-child{border-bottom:0}
.driver .row{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;
  margin-bottom:4px}
.driver .name{font-family:var(--display);font-weight:700;font-size:16.5px;
  letter-spacing:-.015em;text-transform:capitalize}
.driver .pts{font-family:var(--mono);font-size:11px;color:var(--ink-3);
  background:var(--sunk);padding:2px 8px;border-radius:999px}
.driver .detail{color:var(--ink-2);font-size:14px;margin-bottom:13px}
blockquote{margin:0;padding:14px 16px;background:var(--surface-2);
  border:1px solid var(--line);border-left:3px solid var(--teal);
  border-radius:var(--r-sm)}
blockquote p{margin:0;font-size:14.5px;line-height:1.6;color:var(--ink)}
.source{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:11px;
  padding-top:10px;border-top:1px solid var(--line);font-size:11.5px;
  color:var(--ink-3)}
.source .tag{display:inline-flex;align-items:center;gap:5px;font-weight:600;
  color:var(--teal);text-transform:uppercase;letter-spacing:.05em;
  font-size:10.5px}
.source .doc{font-weight:600;color:var(--ink-2)}
.source .id{font-family:var(--mono);font-size:11px}
.nosource{padding:13px 16px;border:1px dashed var(--line-2);
  border-radius:var(--r-sm);font-size:13.5px;color:var(--ink-3);
  background:var(--surface-2)}
.sentiment{display:flex;gap:26px;align-items:center;flex-wrap:wrap;
  padding:20px;border-bottom:1px solid var(--line)}
.ring{position:relative;width:104px;height:104px;flex:none}
.ring svg{transform:rotate(-90deg)}
.ring .val{position:absolute;inset:0;display:grid;place-items:center;
  font-family:var(--display);font-weight:800;font-size:27px;letter-spacing:-.03em}
.sentiment .lbl{font-family:var(--display);font-weight:700;font-size:19px;
  text-transform:capitalize;letter-spacing:-.02em}
.sentiment .exp{font-size:13.5px;color:var(--ink-2);max-width:44ch;margin-top:4px}
.quotes{display:grid;gap:12px;padding:20px}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));
  gap:1px;background:var(--line);border-radius:0 0 var(--r) var(--r);
  overflow:hidden}
.metric{background:var(--surface);padding:17px 20px}
.metric .k{font-size:11.5px;font-weight:600;letter-spacing:.03em;
  text-transform:uppercase;color:var(--ink-3);margin-bottom:8px}
.metric .v{font-family:var(--display);font-weight:800;font-size:25px;
  line-height:1;letter-spacing:-.03em}
.metric .src{font-size:11.5px;color:var(--ink-3);margin-top:7px}
ol.actions{margin:0;padding:20px;list-style:none;counter-reset:a;display:grid;
  gap:12px}
ol.actions li{counter-increment:a;position:relative;padding-left:38px;
  font-size:14.5px}
ol.actions li::before{
  content:counter(a);position:absolute;left:0;top:-1px;width:25px;height:25px;
  border-radius:8px;background:var(--teal-bg);color:var(--teal);
  font-family:var(--display);font-size:12.5px;font-weight:700;display:grid;
  place-items:center;
}
.gaps{padding:20px;font-size:14px;color:var(--ink-2)}
.gaps ul{margin:0;padding-left:19px}
.gaps li{margin:5px 0}
.stagger{animation:rise .46s cubic-bezier(.2,.7,.3,1) backwards}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1}}
@media (prefers-reduced-motion:reduce){.stagger{animation:none}}
@media (max-width:680px){
  .wrap{padding:0 15px 60px}.topbar .inner{padding:12px 15px}
  th{position:static}.count{margin-left:0}
  /* four full-height KPI cards would push the account table ~1400px down on a
     phone; pair them up and tighten so the actual work stays reachable */
  .kpis{grid-template-columns:1fr 1fr;gap:10px}
  .kpi{padding:13px 14px}
  .kpi .k{font-size:10.5px;margin-bottom:6px}
  .kpi .v{font-size:25px}
  .kpi .sub{font-size:11px;margin-top:5px}
  .pagehead p{font-size:14px}
  .field,.field select{width:100%}
  /* the table already scrolls sideways, so give the name column a floor
     rather than letting "Riverside Physical Therapy" wrap onto three lines */
  th:first-child,td:first-child{min-width:196px}
}
@media print{
  .topbar,.backlink,.filters{display:none}
  body{background:#fff}.card{box-shadow:none;break-inside:avoid}
}
"""

THEME_JS = """
(function(){
  // Dark is this tool's house look, so it is the default rather than the
  // system preference; a stored choice always wins and persists.
  var k='rrb-theme',r=document.documentElement,s=localStorage.getItem(k);
  r.setAttribute('data-theme',s==='light'||s==='dark'?s:'dark');
  window.rrbToggle=function(){
    var n=r.getAttribute('data-theme')==='dark'?'light':'dark';
    r.setAttribute('data-theme',n);localStorage.setItem(k,n);
  };
})();
"""

# The tab icon is the same mark as the in-app logo: the pulse glyph on the
# brand teal. Defined here so the app and the static file served to browsers
# cannot drift apart (tests/test_favicon.py asserts they match).
FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" '
    'width="32" height="32" role="img" aria-label="VitalPoint">'
    '<rect width="32" height="32" rx="7" fill="#0d6e66"/>'
    '<path d="M5 16h4.4l2.75-7.7 5.5 15.4 2.75-7.7H27" fill="none" '
    'stroke="#ffffff" stroke-width="2.6" stroke-linecap="round" '
    'stroke-linejoin="round"/></svg>'
)

LOGO = ('<span class="logo"><svg width="17" height="17" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2.4" '
        'stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M2 12h4l2.5-7 5 14 2.5-7h6"/></svg>'
        '</span>')

SUN = ('<svg class="t-sun" width="15" height="15" viewBox="0 0 24 24" '
       'fill="none" stroke="currentColor" stroke-width="2" '
       'stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/>'
       '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2'
       'M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>')

MOON = ('<svg class="t-moon" width="15" height="15" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M20.5 14.2A8.5 8.5 0 1 1 9.8 3.5a6.8 6.8 0 0 0 10.7 10.7Z"/>'
        '</svg>')

THEME_BTN = (f'<button class="theme-btn" onclick="rrbToggle()" '
             f'aria-label="Switch between light and dark theme">'
             f'{SUN}{MOON}'
             f'<span class="t-light">Light</span>'
             f'<span class="t-dark">Dark</span></button>')


def esc(value) -> str:
    return html.escape(str(value))


def pct(value: int) -> str:
    """Signed percent, but never '+0%' — a sign on zero implies a direction
    the number does not actually carry."""
    return f"{value:+d}%" if value else "0%"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def money(n: int) -> str:
    """Abbreviate for KPI tiles: 1_250_000 -> $1.25M."""
    if n >= 1_000_000:
        return f"${n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"${n / 1_000:.0f}K"
    return f"${n}"


def sparkline(values, width=66, height=20) -> str:
    """Inline SVG of a real usage series — data, not decoration."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = width / (len(values) - 1)
    coords = [(i * step, height - 2 - (v - lo) / span * (height - 4))
              for i, v in enumerate(values)]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    stroke = "var(--high)" if values[-1] < values[0] else "var(--teal)"
    area = (f"M0,{height} " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in coords)
            + f" L{width},{height} Z")
    lx, ly = coords[-1]
    return (
        f'<svg class="spark" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" aria-hidden="true">'
        f'<path d="{area}" fill="{stroke}" opacity=".1"/>'
        f'<polyline points="{pts}" fill="none" stroke="{stroke}" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2" fill="{stroke}"/></svg>')


def _topbar(as_of: str, vendor: str) -> str:
    return (
        f'<div class="topbar"><div class="inner">'
        f'<a class="brand" href="/">{LOGO}'
        f'<span class="wordmark">Vital<span>Point</span></span></a>'
        f'<span class="spacer"></span>'
        f'<span class="asof">As of {esc(as_of)}</span>'
        f'{THEME_BTN}</div></div>')


def page(title: str, body: str, as_of: str, vendor: str,
         wrap_class: str = "") -> str:
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(title)}</title>'
        f'<link rel="icon" type="image/svg+xml" href="/favicon.svg">'
        f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link rel="stylesheet" href="{FONTS}">'
        f'<style>{CSS}</style><script>{THEME_JS}</script></head><body>'
        f'{_topbar(as_of, vendor)}'
        f'<div class="wrap {wrap_class}">{body}</div></body></html>')


def _select(name: str, label: str, options, current: str) -> str:
    opts = ['<option value="">All</option>']
    for o in options:
        sel = " selected" if o == current else ""
        opts.append(f'<option value="{esc(o)}"{sel}>{esc(o).title()}</option>')
    return (f'<div class="field"><label for="{name}">{esc(label)}</label>'
            f'<select id="{name}" name="{name}">{"".join(opts)}</select></div>')


HEAD_HTML = (
    '<div class="pagehead"><h1>Renewal Desk</h1>'
    '<p>Every account in the book, scored on usage, support load and '
    'customer sentiment — sorted so the conversations that matter most '
    'this week sit at the top.</p></div>')

TABLE_HEAD = (
    '<thead><tr>'
    '<th>Practice</th><th>Account</th><th>Usage · 15 mo</th>'
    '<th>Satisfaction</th><th>Risk</th><th>Renews</th>'
    '<th class="num">In</th><th class="num">ARR</th>'
    '</tr></thead>')

EMPTY_HTML = ('<div class="empty" id="empty"><strong>No accounts match</strong>'
              'Try widening the filters, or reset to see the full book.</div>')


def _row_html(r, i: int) -> str:
    """One account row of the dashboard table."""
    dcls = " down" if r["declining"] else ""
    scol = ("var(--high)" if r["sat"] < 40
            else "var(--med)" if r["sat"] <= 70 else "var(--low)")
    urgent = " urgent" if r["days"] <= 30 else ""
    return (
        f'<tr class="stagger" style="animation-delay:{min(i, 12) * 18}ms">'
        f'<td><a class="practice" href="/brief/{esc(r["id"])}">'
        f'{esc(r["name"])}</a>'
        f'<div class="place">{esc(r["specialty"].title())} · '
        f'{esc(r["city"])}, {esc(r["state"])}</div></td>'
        f'<td><a class="aid" href="/brief/{esc(r["id"])}">'
        f'{esc(r["id"])}</a></td>'
        f'<td><div class="trend">{sparkline(r["usage"])}'
        f'<span class="delta{dcls}">{pct(r["usage_change"])}</span>'
        f'</div></td>'
        f'<td><div class="sat"><span class="satbar">'
        f'<i style="width:{r["sat"]}%;background:{scol}"></i></span>'
        f'<span class="mono">{r["sat"]}</span></div></td>'
        f'<td><span class="badge {r["level"]}">{r["level"]}</span></td>'
        f'<td class="mono">{esc(r["renewal"])}</td>'
        f'<td class="num"><span class="soon{urgent}">{r["days"]}d</span></td>'
        f'<td class="num mono">${r["arr"]:,}</td></tr>')


def _table_html(rows) -> str:
    if not rows:
        return EMPTY_HTML
    trs = "".join(_row_html(r, i) for i, r in enumerate(rows))
    return (f'<div class="scroll"><table>{TABLE_HEAD}'
            f'<tbody>{trs}</tbody></table></div>')


def _kpis_html(stats) -> str:
    return (
        f'<div class="kpis">'
        f'<div class="kpi risk stagger"><div class="k">At high risk</div>'
        f'<div class="v">{stats["high"]}</div>'
        f'<div class="sub">of {stats["total"]} accounts in the book</div></div>'
        f'<div class="kpi stagger" style="animation-delay:60ms">'
        f'<div class="k">ARR at risk</div>'
        f'<div class="v">{money(stats["arr_at_risk"])}</div>'
        f'<div class="sub">of {money(stats["arr_total"])} total ARR</div></div>'
        f'<div class="kpi stagger" style="animation-delay:120ms">'
        f'<div class="k">Renewing in 30 days</div>'
        f'<div class="v">{stats["soon"]}</div>'
        f'<div class="sub">{stats["soon_high"]} of them high risk</div></div>'
        f'<div class="kpi stagger" style="animation-delay:180ms">'
        f'<div class="k">Median satisfaction</div>'
        f'<div class="v">{stats["median_sat"]}</div>'
        f'<div class="sub">out of 100, from ticket &amp; QBR tone</div>'
        f'</div></div>')


def dashboard_page(rows, stats, specialties, states, current, vendor, as_of):
    head = HEAD_HTML

    kpis = _kpis_html(stats)

    sort = current["sort"]
    filters = (
        f'<form class="filters" method="get">'
        f'{_select("specialty", "Specialty", specialties, current["specialty"])}'
        f'{_select("state", "State", states, current["state"])}'
        f'{_select("risk", "Risk level", ["high", "medium", "low"], current["risk"])}'
        f'<div class="field"><label for="sort">Sort by</label>'
        f'<select id="sort" name="sort">'
        f'<option value="risk"{" selected" if sort == "risk" else ""}>'
        f'Risk, then renewal date</option>'
        f'<option value="renewal"{" selected" if sort == "renewal" else ""}>'
        f'Soonest renewal</option>'
        f'<option value="arr"{" selected" if sort == "arr" else ""}>'
        f'Largest ARR</option></select></div>'
        f'<button class="btn" type="submit">Apply</button>'
        f'<a class="btn ghost" href="/">Reset</a>'
        f'<div class="count"><b>{len(rows)}</b> '
        f'{"account" if len(rows) == 1 else "accounts"} shown</div></form>')

    table = _table_html(rows)

    body = (head + kpis + '<div class="card">' + filters + table + '</div>')
    return page("Renewal Desk — VitalPoint Software", body, as_of, vendor)


def _evidence(cit) -> str:
    if cit is None:
        return ('<div class="nosource">No document in this account’s corpus '
                'supports this claim, so it is reported as a metric only — '
                'never as a quote.</div>')
    # excerpts are sliced to a fixed width upstream; mark the cut so a
    # mid-sentence stop never reads as the end of the quote
    ellipsis = "…" if len(cit.excerpt) >= 180 else ""
    return (
        f'<blockquote><p>“{esc(cit.excerpt)}{ellipsis}”</p>'
        f'<div class="source"><span class="tag">Source</span>'
        f'<span class="doc">{esc(cit.title)}</span><span>·</span>'
        f'<span>{esc(cit.doc_date)}</span><span>·</span>'
        f'<span class="id">{esc(cit.doc_id)}</span></div></blockquote>')


UNKNOWN_TEXT = {
    "qbr_notes": "No QBR notes on file — sentiment rests on support tickets alone.",
    "support_tickets": "No support tickets on file — no support signal available.",
}

SENTIMENT_EXPLAIN = {
    "frustrated": "Language across tickets and QBR notes trends negative — "
                  "escalation, repetition, and churn wording.",
    "neutral": "Tone is mixed or transactional; no strong positive or negative "
               "signal in the written record.",
    "happy": "Written record skews positive — praise, smooth adoption, and "
             "low-friction requests.",
    "unknown": "Not enough narrative text on file to judge tone.",
}


def _ring(score: int, color: str) -> str:
    circ = 2 * 3.14159 * 45
    dash = circ * score / 100
    # a zero score draws no arc at all — a round-capped zero-length dash
    # renders as a stray dot that reads as a glitch
    arc = ("" if score <= 0 else
           f'<circle cx="52" cy="52" r="45" fill="none" stroke="{color}" '
           f'stroke-width="9" stroke-linecap="round" '
           f'stroke-dasharray="{dash:.1f} {circ:.1f}"/>')
    return (
        f'<div class="ring"><svg width="104" height="104" viewBox="0 0 104 104">'
        f'<circle cx="52" cy="52" r="45" fill="none" stroke="var(--sunk)" '
        f'stroke-width="9"/>{arc}</svg>'
        f'<div class="val" style="color:{color}">{score}</div></div>')


def brief_page(acct, b, usage, actions, vendor, as_of):
    lvl = b.risk.level
    tone = {"high": "var(--high)", "medium": "var(--med)",
            "low": "var(--low)"}[lvl]
    meter_pct = min(100, round(b.risk.points / 60 * 100))
    sat = b.satisfaction
    scol = ("var(--high)" if sat.score < 40
            else "var(--med)" if sat.score <= 70 else "var(--low)")

    hero = (
        f'<a class="backlink" href="/">← All accounts</a>'
        f'<div class="card hero stagger">'
        f'<span class="eyebrow">Renewal Risk Brief</span>'
        f'<h1>{esc(acct["name"])}</h1><div class="chips">'
        f'<span class="chip">{esc(acct["specialty"].title())}</span>'
        f'<span class="chip">{esc(acct["city"])}, {esc(acct["state"])}</span>'
        f'<span class="chip"><b>{acct["seats"]}</b> seats</span>'
        f'<span class="chip">ARR <b>${acct["arr"]:,}</b></span>'
        f'<span class="chip">Renews <b>{esc(acct["contract_end"])}</b></span>'
        f'<span class="chip">Auto-renew '
        f'<b>{"on" if acct["auto_renew"] else "off"}</b></span>'
        f'</div></div>')

    verdict = (
        f'<div class="card verdict {lvl} stagger" style="animation-delay:60ms">'
        f'<div><div class="lvl">{lvl.upper()} RISK</div>'
        f'<div class="meta">{plural(b.risk.points, "risk point")} · '
        f'{plural(b.signals.days_to_renewal, "day")} to renewal</div></div>'
        f'<div class="meter"><i style="width:{meter_pct}%;background:{tone}"></i>'
        f'</div></div>')

    if b.risk.drivers:
        items = "".join(
            f'<div class="driver"><div class="row">'
            f'<span class="name">{esc(d.key.replace("_", " "))}</span>'
            f'<span class="pts">+{d.points} pts</span></div>'
            f'<div class="detail">{esc(d.detail)}</div>'
            f'{_evidence(b.driver_evidence.get(d.key))}</div>'
            for d in b.risk.drivers)
    else:
        items = ('<div class="card-body"><div class="nosource">No active risk '
                 'drivers detected — usage, support load and sentiment are all '
                 'within range.</div></div>')
    drivers = (
        f'<section class="card stagger" style="animation-delay:120ms">'
        f'<div class="card-head"><h2>Why this account is at risk</h2></div>'
        f'{items}</section>')

    quotes = "".join(
        f'<blockquote><p>“{esc(q.text)}”</p><div class="source">'
        f'<span class="tag">Quoted from</span>'
        f'<span class="doc">{esc(q.title)}</span><span>·</span>'
        f'<span>{esc(q.doc_date)}</span></div></blockquote>'
        for q in sat.quotes)
    sentiment = (
        f'<section class="card stagger" style="animation-delay:180ms">'
        f'<div class="card-head"><h2>Customer sentiment</h2></div>'
        f'<div class="sentiment">{_ring(sat.score, scol)}'
        f'<div><div class="lbl" style="color:{scol}">{esc(sat.label)}</div>'
        f'<div class="exp">{esc(SENTIMENT_EXPLAIN[sat.label])}</div></div>'
        f'</div>'
        f'<div class="quotes">{quotes or _evidence(None)}</div></section>')

    s = b.signals
    history = (
        f'<section class="card stagger" style="animation-delay:240ms">'
        f'<div class="card-head"><h2>Recent history</h2></div>'
        f'<div class="metrics">'
        f'<div class="metric"><div class="k">Usage trend</div>'
        f'<div class="v">{pct(round(s.usage_change_pct))}</div>'
        f'<div class="src">logins, quarter over quarter</div></div>'
        f'<div class="metric"><div class="k">Support load</div>'
        f'<div class="v">{s.avg_tickets_per_month:.1f}</div>'
        f'<div class="src">tickets/mo · {s.open_high_severity} open high-sev</div>'
        f'</div>'
        f'<div class="metric"><div class="k">Seat utilization</div>'
        f'<div class="v">{s.seat_utilization:.0%}</div>'
        f'<div class="src">active users ÷ paid seats</div></div>'
        f'<div class="metric"><div class="k">15-month usage</div>'
        f'<div class="v">{sparkline(usage, 116, 28)}</div>'
        f'<div class="src">monthly logins</div></div></div></section>')

    acts = "".join(f"<li>{esc(a)}</li>" for a in actions)
    actions_html = (
        f'<section class="card stagger" style="animation-delay:300ms">'
        f'<div class="card-head"><h2>Recommended actions</h2></div>'
        f'<ol class="actions">{acts}</ol></section>')

    if b.unknowns:
        lis = "".join(
            f'<li>{esc(UNKNOWN_TEXT.get(u, "No evidence found for " + u.replace("_", " ") + "."))}</li>'
            for u in b.unknowns)
        gap_body = f'<ul>{lis}</ul>'
    else:
        gap_body = "Every signal in this brief is backed by a cited document."
    gaps = (
        f'<section class="card stagger" style="animation-delay:360ms">'
        f'<div class="card-head"><h2>What we don’t know</h2></div>'
        f'<div class="gaps">{gap_body}</div></section>')

    body = hero + verdict + drivers + sentiment + history + actions_html + gaps
    return page(f"{acct['name']} — Renewal Risk Brief", body, as_of, vendor,
                "brief-wrap")
