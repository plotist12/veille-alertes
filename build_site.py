# build_site.py — même contenu, design plus pro (thème cybersécurité)

import re, pathlib
from string import Template

try:
    import markdown  # pip install markdown
except ImportError:
    raise SystemExit("Installe 'markdown' : pip install markdown")

ROOT = pathlib.Path(__file__).parent
OUTS = [ROOT / "output", ROOT / "google-alerts-summarizer" / "output"]
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)
(DOCS / ".nojekyll").write_text("", encoding="utf-8")

STYLE = """
<style>
:root{
  --bg:#0b0f19; --panel:#0f1526; --card:#0f1730; --line:#152449;
  --text:#e6eefc; --muted:#9fb0c9; --accent:#00e676; --accent2:#64ffda;
  --code:#0b1226;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:radial-gradient(1000px 480px at 10% -10%, rgba(0,230,118,.08), transparent),
             radial-gradient(800px 400px at 120% 20%, rgba(100,255,218,.06), transparent),
             linear-gradient(180deg,#0b0f19 0%,#0a0e18 100%);
  color:var(--text);
  font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
}
a{color:var(--accent2);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:980px;margin:0 auto;padding:28px}
header{
  position:sticky;top:0;z-index:10;
  background:rgba(10,14,24,.75); backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);
}
.brand{display:flex;align-items:center;gap:12px}
.logo{width:28px;height:28px;border-radius:8px;
  background:radial-gradient(140px at 35% 35%, #1cffb6, #00e676 42%, #0b0f19 65%);
  border:1px solid #17604e; box-shadow:0 0 22px rgba(0,230,118,.22) inset;
}
h1{font-size:22px;margin:0}
.sub{color:var(--muted);font-size:14px;margin-top:2px}

main{padding-top:16px}
.container{
  background:var(--panel);
  border:1px solid var(--line);
  border-radius:16px;
  padding:22px;
  box-shadow:0 8px 28px rgba(0,0,0,.25);
}
.page-title{display:flex;align-items:center;gap:10px;margin:0 0 10px}
.page-title .dot{width:10px;height:10px;border-radius:50%;background:var(--accent)}

.content{padding:10px 6px}
.content h1{display:none} /* on masque le # Résumés – YYYY-MM-DD du markdown */
.content h2{
  font-size:20px;margin:18px 0 6px;
}
.content p{margin:10px 0}
.content em{color:var(--muted)}
.content ul{margin:8px 0 14px 22px}
.content li{margin:4px 0}
.content blockquote{
  margin:12px 0;padding:10px 14px;border-left:3px solid var(--accent);
  background:#0c142b;border-radius:8px;color:#cfe3ff;
}
.content code{
  background:var(--code); border:1px solid #16284e; border-radius:6px;
  padding:2px 6px; font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.content pre code{
  display:block; padding:14px; overflow:auto;
}

.card{
  background:var(--card); border:1px solid var(--line);
  border-left:4px solid var(--accent);
  border-radius:14px; padding:14px; margin:16px 0;
}
.card h2{margin-top:0}
.footer{
  color:var(--muted); font-size:13px; margin-top:22px; text-align:center
}
</style>
"""

TPL = Template("""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>$title</title>
$style
<body>
<header>
  <div class="wrap">
    <div class="brand">
      <div class="logo" aria-hidden="true"></div>
      <div>
        <h1>Veille Cybersécurité</h1>
        <div class="sub">$subtitle</div>
      </div>
    </div>
  </div>
</header>
<main>
  <div class="wrap">
    <div class="container">
      <h2 class="page-title"><span class="dot"></span> $title</h2>
      <div class="content">$body</div>
      <div class="footer">Publié automatiquement – design thème cyber.</div>
    </div>
  </div>
</main>
</body>
""")

def find_md_files():
    files = []
    for base in OUTS:
        if not base.exists(): continue
        files += sorted([p for p in base.glob("*.md") if re.match(r"\\d{4}-\\d{2}-\\d{2}\\.md$", p.name)])
    if not files:
        for base in OUTS:
            p = base / "latest.md"
            if p.exists(): return [p]
    return files

def md_to_html(md_text: str) -> str:
    # on ajoute une classe .card autour de chaque article (## Titre)
    import markdown
    html = markdown.markdown(md_text, extensions=["extra","tables"])
    # convertir chaque bloc d'article en .card (h2 + ce qui suit jusqu'au prochain h2)
    parts = re.split(r"(<h2>.*?</h2>)", html, flags=re.S)
    if len(parts) <= 1:
        return html
    out = []
    for i in range(1, len(parts), 2):
        h2 = parts[i]
        body = parts[i+1] if i+1 < len(parts) else ""
        out.append(f'<section class="card">{h2}{body}</section>')
    # conserver le h1 initial (caché via CSS) au début
    prefix = parts[0]
    return prefix + "".join(out)

def write_page(path: pathlib.Path, title: str, subtitle: str, md_text: str):
    body = md_to_html(md_text)
    html = TPL.safe_substitute(title=title, subtitle=subtitle, style=STYLE, body=body)
    path.write_text(html, encoding="utf-8")

def main():
    files = find_md_files()
    if not files:
        write_page(DOCS / "index.html", "Aucun article", "Rien à afficher pour le moment.", "_Aucun article._")
        print("Aucun markdown trouvé.")
        return

    days = []
    for p in files:
        day = p.stem if re.match(r"\\d{4}-\\d{2}-\\d{2}$", p.stem) else "Aujourd'hui"
        md = p.read_text(encoding="utf-8")
        write_page(DOCS / f"{day}.html", f"Résumés – {day}", "Synthèse quotidienne", md)
        days.append(day)

    # index
    days = sorted(set(days), reverse=True)
    links_md = "\\n".join(f"- [{d}](./{d}.html)" for d in days)
    index_md = f"# Historique\\n\\n{links_md}"
    write_page(DOCS / "index.html", "Historique – Veille cybersécurité", "Accès aux pages quotidiennes", index_md)

    print("OK : rendu stylé généré dans docs/")

if __name__ == "__main__":
    main()
