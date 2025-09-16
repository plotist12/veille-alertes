# build_site.py
# Magazine cybersécurité : transforme output/*.md -> docs/*.html + index + all.html
# - Design sombre "cyber"
# - Une page par jour + index
# - Filtres par tags + recherche côté navigateur
# - Détection de tags via mots-clés du titre/résumé

import re, pathlib, html
from urllib.parse import urlparse

try:
    import markdown  # pip install markdown
except ImportError:
    raise SystemExit("Installe le paquet 'markdown' :  pip install markdown")

ROOT = pathlib.Path(__file__).parent
OUT  = ROOT / "output"
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)
(DOCS / ".nojekyll").write_text("", encoding="utf-8")  # pas de Jekyll

md = markdown.Markdown(extensions=["extra", "tables"])

# ---------- Style & shell ----------
STYLE = r"""
<style>
:root{
  --bg:#0b0f19; --panel:#0f1526; --card:#101933; --line:#1b2b55;
  --text:#e7ecf7; --muted:#9aa6bb; --accent:#00e676; --accent2:#64ffda; --chip:#142447;
}
*{box-sizing:border-box} html,body{margin:0;padding:0}
body{background:linear-gradient(180deg,#0b0f19 0%,#0a0e1a 100%);color:var(--text);
  font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent2);text-decoration:none}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
header{position:sticky;top:0;background:rgba(15,21,38,.85);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);z-index:5}
.brand{display:flex;gap:12px;align-items:center}
.logo{width:28px;height:28px;border-radius:8px;background:radial-gradient(120px at 30% 30%,#1cffb6,#00e676 40%,#0b0f19 60%);
  border:1px solid #155e4b;box-shadow:0 0 18px rgba(0,230,118,.25) inset}
h1{font-size:22px;margin:0}
.sub{color:var(--muted);font-size:14px;margin-top:2px}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}
.input{flex:1 1 260px;display:flex;align-items:center;background:#0d1427;border:1px solid var(--line);
  border-radius:12px;padding:10px 12px}
.input input{all:unset;width:100%;color:var(--text)}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{background:var(--chip);border:1px solid var(--line);color:#cfe7ff;font-size:12px;
  padding:6px 10px;border-radius:999px;cursor:pointer;user-select:none}
.chip.active{outline:2px solid var(--accent); box-shadow:0 0 0 3px rgba(0,230,118,.12)}
.grid{display:grid;grid-template-columns:1fr;gap:14px;margin-top:18px}
@media(min-width:860px){.grid{grid-template-columns:1fr 1fr}}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);
  border-radius:16px; padding:16px;box-shadow:0 6px 22px rgba(0,0,0,.25)}
.card h2{margin:0 0 8px;font-size:18px;line-height:1.3}
.meta{display:flex;gap:10px;align-items:center;color:var(--muted);font-size:12px;margin-bottom:10px}
.meta img{width:14px;height:14px;border-radius:3px;vertical-align:middle}
.meta .dot{width:4px;height:4px;background:var(--line);border-radius:50%}
.actions{margin-top:10px;display:flex;gap:10px}
.btn{display:inline-block;padding:9px 12px;background:#0e1a36;border:1px solid var(--line);
  color:#cfe7ff;border-radius:10px}
.btn.primary{background:linear-gradient(90deg,#00e676,#64ffda);color:#0b101b;border:0;font-weight:600}
ul{margin:0 0 0 18px}
footer{border-top:1px solid var(--line);margin-top:24px}
.daynav{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.daynav a{padding:8px 12px;border:1px solid var(--line);border-radius:10px;background:#0d1427}
.empty{color:var(--muted);padding:16px;border:1px dashed var(--line);border-radius:12px;background:#0d1427}
</style>
"""

SHELL = """<!doctype html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>{style}</head><body>
<header><div class="wrap">
  <div class="brand">
    <div class="logo" aria-hidden="true"></div>
    <div>
      <h1>{brand}</h1>
      <div class="sub">{subtitle}</div>
    </div>
  </div>
  {toolbar}
</div></header>
<main><div class="wrap">
  {daynav}
  {content}
</div></main>
<footer><div class="wrap">Publié automatiquement avec GitHub Pages – veille cybersécurité.</div></footer>
<script>
const q = document.querySelector('#q');
const chips = [...document.querySelectorAll('.chip')];
const cards = [...document.querySelectorAll('.card')];

function applyFilters(){
  const term = (q?.value||'').toLowerCase().trim();
  const activeTags = chips.filter(c=>c.classList.contains('active')).map(c=>c.dataset.tag);
  cards.forEach(card=>{
    const hay = card.dataset.search;
    const tags = (card.dataset.tags||'').split(',');
    const hasAll = activeTags.every(t=>tags.includes(t));
    const okTerm = !term || hay.includes(term);
    card.style.display = (hasAll && okTerm) ? '' : 'none';
  });
}
if(q){ q.addEventListener('input', applyFilters); }
chips.forEach(c=>c.addEventListener('click', ()=>{ c.classList.toggle('active'); applyFilters(); }));
</script>
</body></html>"""

# ---------- Parsing du markdown du jour ----------
def parse_articles(md_text: str):
    """Retourne une liste d'objets: title, link, source, pub, md_segment, text_for_tags"""
    lines = md_text.splitlines()
    blocks, cur = [], []
    for ln in lines:
        if ln.startswith("## "):
            if cur: blocks.append("\n".join(cur).strip())
            cur = [ln]
        else:
            if cur: cur.append(ln)
    if cur: blocks.append("\n".join(cur).strip())

    items = []
    for seg in blocks:
        m = re.search(r"^## \[(?P<title>.+?)\]\((?P<link>.+?)\)", seg, re.M|re.S)
        if not m: 
            title = "(Sans titre)"; link = ""
        else:
            title = m.group("title").strip()
            link  = m.group("link").strip()
        # métadonnées en italique
        meta_m = re.search(r"^\*(?P<meta>.+?)\*\s*$", seg, re.M)
        src = pub = ""
        if meta_m:
            meta = meta_m.group("meta")
            for part in [p.strip() for p in meta.split("|")]:
                if part.lower().startswith("source"):
                    src = part.split(":",1)[-1].strip()
                elif part.lower().startswith("publication"):
                    pub = part.split(":",1)[-1].strip()
        # texte brut pour recherche / tags
        bullets = "\n".join([ln for ln in seg.splitlines() if ln.strip().startswith("- ")])
        text_for_tags = (title + " " + bullets).lower()
        items.append({
            "title": title, "link": link, "source": src, "pub": pub,
            "segment": seg, "text": text_for_tags
        })
    return items

# ---------- Tagging heuristique ----------
TAG_RULES = [
    ("attaque",  r"\b(attaque|attaquant|intrus|ddos|intrusion)\b"),
    ("ransomware", r"\bransomware|ran[cs]ongiciel\b"),
    ("vulnérabilité", r"\b(vulnérabilit|faille|cve)\b"),
    ("phishing", r"\b(phishing|hame[cç]onnage)\b"),
    ("OT/indus", r"\b(OT|industriel|SCADA|ICS)\b"),
    ("IA", r"\b(IA|intelligence artificielle|machine learning|LLM)\b"),
    ("cloud", r"\b(cloud|saas|azure|aws|gcp)\b"),
    ("réglementation", r"\b(RGPD|NIS|ANSSI|conformit|r[eé]glement)\b"),
    ("formation", r"\b(formation|sensibilisation|awareness)\b"),
]

def tags_for(text: str):
    tags = []
    for label, patt in TAG_RULES:
        if re.search(patt, text, re.I):
            tags.append(label)
    return tags

def favicon_url(url: str):
    try:
        host = urlparse(url).netloc
        return f"https://www.google.com/s2/favicons?domain={host}&sz=64"
    except Exception:
        return ""

# ---------- Rendering ----------
def render_toolbar(with_filters=True):
    if not with_filters:
        return ""
    chips = "".join([f'<span class="chip" data-tag="{html.escape(t)}">{html.escape(t)}</span>' for t,_ in TAG_RULES])
    return f"""
    <div class="toolbar">
      <label class="input" title="Rechercher un titre, un point clé, une source...">
        🔍&nbsp;<input id="q" placeholder="Rechercher (titre, points, source)"/>
      </label>
      <div class="chips">{chips}</div>
    </div>
    """

def render_cards(items):
    if not items:
        return '<div class="empty">Aucun article pour ce jour.</div>'
    out = []
    for it in items:
        seg_html = markdown.markdown(it["segment"], extensions=["extra","tables"])
        seg_html = re.sub(r"<p><em>.*?</em></p>", "", seg_html, flags=re.S)  # enlève la ligne meta en italique
        title_html = re.search(r"<h2>(.*?)</h2>", seg_html, re.S)
        if title_html:
            body_html = seg_html.replace(title_html.group(0), "")
        else:
            body_html = seg_html
        tag_list = tags_for(it["text"])
        tags_attr = ",".join(tag_list)
        chips = " ".join(f'<span class="chip">{html.escape(t)}</span>' for t in tag_list)
        fav = favicon_url(it["link"]) if it["link"] else ""
        src = html.escape(it["source"]) if it["source"] else urlparse(it["link"]).netloc.replace("www.","")
        pub = html.escape(it["pub"]) if it["pub"] else ""
        meta = []
        if fav: meta.append(f'<img src="{fav}" alt=""> {src}')
        elif src: meta.append(src)
        if pub: meta.append(pub)
        meta_html = ' <span class="dot"></span> '.join(meta)
        out.append(
f'''<article class="card" data-tags="{html.escape(tags_attr)}" data-search="{html.escape((it["title"]+" "+it["text"]).lower())}">
  <div class="meta">{meta_html}</div>
  <h2><a href="{html.escape(it["link"])}" target="_blank" rel="noopener">{html.escape(it["title"])}</a></h2>
  {body_html}
  <div class="actions">
    <a class="btn primary" href="{html.escape(it["link"])}" target="_blank" rel="noopener">Lire l’article</a>
    {('<span class="btn">'+chips+'</span>') if chips else ''}
  </div>
</article>'''
        )
    return '<section class="grid">' + "\n".join(out) + "</section>"

def build_day_page(day: str, items):
    toolbar = render_toolbar(True)
    days = sorted([p.stem for p in DOCS.glob("*.html") if re.match(r"\d{4}-\d{2}-\d{2}\.html$", p.name)], reverse=True)
    daynav = ""
    if days:
        links = " ".join(f'<a href="./{d}.html">{d}</a>' for d in days[:14])
        daynav = f'<div class="daynav"><strong>Jours récents :</strong> {links}</div>'
    html_page = SHELL.format(
        title=f"Veille cybersécurité – {day}",
        style=STYLE, brand="Veille Cybersécurité",
        subtitle=f"Résumés automatiques – {day}",
        toolbar=toolbar, daynav=daynav,
        content=render_cards(items))
    (DOCS / f"{day}.html").write_text(html_page, encoding="utf-8")

def build_index(days):
    links = "\n".join(f'<li><a href="./{d}.html">{d}</a></li>' for d in days)
    content = f'<section class="grid"><div class="card"><h2>Jours disponibles</h2><ul>{links or "<li>(vide)</li>"}</ul></div></section>'
    html_page = SHELL.format(
        title="Veille cybersécurité – Index",
        style=STYLE, brand="Veille Cybersécurité",
        subtitle="Historique quotidien",
        toolbar=render_toolbar(False), daynav="",
        content=content)
    (DOCS / "index.html").write_text(html_page, encoding="utf-8")

def build_all(items):
    html_page = SHELL.format(
        title="Veille cybersécurité – Historique",
        style=STYLE, brand="Veille Cybersécurité",
        subtitle="Tous les articles connus",
        toolbar=render_toolbar(True), daynav="",
        content=render_cards(items))
    (DOCS / "all.html").write_text(html_page, encoding="utf-8")

# ---------- pipeline ----------
def parse_day_file(path: pathlib.Path):
    text = path.read_text(encoding="utf-8")
    return parse_articles(text)

def main():
    # 1) pages par jour
    day_files = sorted([p for p in OUT.glob("*.md") if p.name not in ("all_articles.md","latest.md")])
    all_items = []
    days = []
    for p in day_files:
        day = p.stem
        items = parse_day_file(p)
        build_day_page(day, items)
        all_items.extend(items)
        days.append(day)
    days.sort(reverse=True)
    build_index(days)

    # 2) page "all" (récents d'abord)
    build_all(all_items[::-1])

    print("OK : pages générées dans docs/ (index, YYYY-MM-DD, all.html)")

if __name__ == "__main__":
    main()
