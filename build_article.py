"""Render the experiment article using the installed Markdown package."""
from pathlib import Path
import argparse
import markdown

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pilot', action='store_true', help='Build the powered pilot article.')
args = parser.parse_args()
stem = 'pilot-article' if args.pilot else 'article'
source = (ROOT / 'docs' / f'{stem}.md').read_text()
converter = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'])
body = converter.convert(source)
page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The escape problem | Research notes</title>
<style>
:root{color-scheme:light;--ink:#252b33;--muted:#657080;--line:#dce0e5;--blue:#24628b}
*{box-sizing:border-box}body{margin:0;background:#fafbfc;color:var(--ink);font:19px/1.75 Georgia,'Times New Roman',serif}a{color:var(--blue);text-underline-offset:.2em}a:focus-visible{outline:3px solid #bc7135;outline-offset:4px}header{background:#080914;color:#f2efea;padding:22px max(5vw,24px);display:flex;justify-content:space-between;font:14px/1.5 -apple-system,BlinkMacSystemFont,sans-serif}header a{color:#f2efea}.layout{max-width:1260px;margin:0 auto;display:grid;grid-template-columns:230px minmax(0,820px);gap:64px;padding:70px 32px 110px}aside{font:12px/1.6 -apple-system,BlinkMacSystemFont,sans-serif}aside .toc{position:sticky;top:30px;max-height:90vh;overflow:auto}aside ul{padding:0;list-style:none}aside li{margin:10px 0}aside li li{margin-left:0}aside>div>ul>li>a{font-weight:600}aside a{text-decoration:none;color:var(--muted)}aside a:hover{color:var(--blue)}article{min-width:0}h1{text-wrap:balance;font-weight:400;font-size:clamp(54px,6vw,88px);line-height:1.04;letter-spacing:-.055em;margin:0 0 24px}h2{font-weight:400;font-size:32px;line-height:1.25;letter-spacing:-.025em;margin:58px 0 22px;scroll-margin-top:28px}h1+h2{margin-top:0;font-size:26px;color:var(--muted)}p{margin:0 0 24px}strong{font-weight:700}img{width:100%;height:auto;border-radius:3px;display:block}p:has(>img){margin:36px 0 12px}em{font-size:16px;color:var(--muted)}pre{background:#101622;color:#e4ebf2;padding:24px;overflow:auto;font:13px/1.8 ui-monospace,Menlo,monospace;border-radius:4px}code{font: .83em ui-monospace,Menlo,monospace;overflow-wrap:anywhere}pre code{font:inherit}table{font:13px/1.55 -apple-system,BlinkMacSystemFont,sans-serif;border-collapse:collapse;width:100%;margin:28px 0}th,td{text-align:left;border-bottom:1px solid var(--line);padding:13px 10px;vertical-align:top}th{color:#3a495b;font-weight:600;background:#eef1f4}td:first-child{font-weight:500}blockquote{margin:28px 0;border-left:3px solid #bc7135;padding-left:22px}footer{border-top:1px solid var(--line);padding:30px;text-align:center;font:13px/1.5 -apple-system,BlinkMacSystemFont,sans-serif;color:var(--muted)}
@media(max-width:1000px){.layout{display:block;max-width:840px;padding:42px 24px 70px}aside{display:none}}
@media(max-width:600px){body{font-size:17px}.layout{padding:35px 20px 60px}h2{font-size:28px}table{font-size:11px;display:block;overflow:auto}pre{font-size:11px;padding:15px}header{font-size:12px;gap:18px}}
@media print{header,aside,footer{display:none}.layout{display:block;padding:0}body{font-size:11pt;background:white}h1{font-size:36pt}h2{font-size:20pt;page-break-after:avoid}pre{white-space:pre-wrap;background:#eee;color:#111}a{color:inherit}img,table{break-inside:avoid}}
</style></head><body><header><span>Black Hole Flight Lab / Research notes</span><a href="/">Enter the observatory</a></header><div class="layout"><aside aria-label="Article contents">'''+converter.toc+'</aside><article>'+body+'</article></div><footer>Measured results, executable checks, explicit limits. Local experiment.</footer></body></html>'
if args.pilot:
    page = page.replace('The escape problem | Research notes', 'Can AI escape a black hole? | Research notes')
    page = page.replace('href="/"', 'href="/pilot"')
(ROOT / 'docs' / f'{stem}.html').write_text(page)
print(f'Wrote docs/{stem}.html')
