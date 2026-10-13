"""Build the standalone web page from web/template.html.

Inlines web/deadleg.js and the Excel/Python/JS cross-check figures
(crosscheck/excel_vs_python.json) so the page is a single file that runs
offline (fonts fall back to local serif and sans faces).

    python web/build_page.py                 # writes web/deadleg.html
    python web/build_page.py --fragment out  # also writes the body-only version used for publishing
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEAD = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')


def fragment() -> str:
    tpl = (HERE / "template.html").read_text()
    js = (HERE / "deadleg.js").read_text()
    xc = json.loads((HERE.parent / "crosscheck" / "excel_vs_python.json").read_text())
    keep = [{k: c[k] for k in ("id", "t45", "max_dTout_excel_python", "max_dTout_excel_js")} for c in xc]
    return tpl.replace("/*DEADLEG_JS*/", js).replace("/*XCHECK_JSON*/", json.dumps(keep))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragment", help="also write the body-only page here")
    a = ap.parse_args()
    frag = fragment()
    head, body = frag.split("<div class=\"page\">", 1)
    page = HEAD + head + "</head>\n<body>\n<div class=\"page\">" + body + "</body>\n</html>\n"
    (HERE / "deadleg.html").write_text(page)
    print("wrote", HERE / "deadleg.html")
    if a.fragment:
        Path(a.fragment).write_text(frag)
        print("wrote", a.fragment)


if __name__ == "__main__":
    main()
