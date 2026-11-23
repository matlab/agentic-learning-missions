"""Render the saved calibration Markdown as a standalone, printable HTML packet."""

import argparse
import hashlib
import html
from pathlib import Path
import re


def inline(text, source):
    result, end = [], 0
    pattern = r"`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)"
    for match in re.finditer(pattern, text):
        result.append(html.escape(text[end:match.start()]))
        if match.group(1) is not None:
            result.append("<code>" + html.escape(match.group(1)) + "</code>")
        elif match.group(2) is not None:
            result.append("<strong>" + html.escape(match.group(2)) + "</strong>")
        else:
            label, target = match.group(3), match.group(4)
            url = target if target.startswith("https://") else (source.parent / target).resolve().as_uri()
            result.append(f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>')
        end = match.end()
    result.append(html.escape(text[end:]))
    return "".join(result)


def render_markdown(text, source):
    """Handle the headings, paragraphs, lists and tables used by this document."""
    lines = text.splitlines()
    result, index = [], 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("# "):
            result.append("<h1>" + inline(line[2:], source) + "</h1>")
        elif line.startswith("## "):
            title = line[3:]
            section = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            result.append(f'<h2 id="{section}">' + inline(title, source) + "</h2>")
        elif line.startswith("|"):
            table = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                row = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", cell) for cell in row):
                    table.append(row)
                index += 1
            if len({len(row) for row in table}) != 1:
                raise ValueError("Inconsistent Markdown table columns")
            table_class = ' class="case-table"' if table[0][0] == "Case" else ""
            result.append('<table' + table_class + '><thead><tr>' + "".join("<th>" + inline(cell, source) + "</th>" for cell in table[0]) + "</tr></thead><tbody>")
            for row in table[1:]:
                result.append("<tr>" + "".join("<td>" + inline(cell, source) + "</td>" for cell in row) + "</tr>")
            result.append("</tbody></table>")
            continue
        elif re.match(r"\d+\. ", line):
            result.append("<ol>")
            while index < len(lines) and re.match(r"\d+\. ", lines[index].strip()):
                result.append("<li>" + inline(re.sub(r"^\d+\. ", "", lines[index].strip()), source) + "</li>")
                index += 1
            result.append("</ol>")
            continue
        else:
            paragraph = [line]
            while index + 1 < len(lines) and lines[index + 1].strip() and not re.match(r"^(#|\||\d+\. )", lines[index + 1].strip()):
                index += 1
                paragraph.append(lines[index].strip())
            result.append("<p>" + inline(" ".join(paragraph), source) + "</p>")
        index += 1
    return "\n".join(result)


STYLE = """
@page { size: Letter; margin: .58in .55in .65in; }
* { box-sizing: border-box; }
body { font: 10pt/1.4 "Segoe UI", Arial, sans-serif; color: #202d36; margin: 0; }
h1 { color: #004b87; font-size: 25pt; line-height: 1.16; margin: 12pt 0 15pt; }
h2 { color: #004b87; font-size: 16pt; margin: 20pt 0 9pt; break-after: avoid; }
p { margin: 0 0 9pt; orphans: 3; widows: 3; }
li { margin-bottom: 7pt; break-inside: avoid; }
ol { padding-left: 18pt; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; margin: 12pt 0; font-size: 9pt; line-height: 1.35; }
th, td { text-align: left; vertical-align: top; border: .6pt solid #bcc8cf; padding: 7pt; overflow-wrap: anywhere; }
th { background: #e9f1f6; color: #004b87; font-weight: 650; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th:first-child, td:first-child { width: 23%; }
.case-table th, .case-table td { padding: 3.5pt 6pt; }
code { font-family: Consolas, monospace; font-size: .9em; overflow-wrap: anywhere; }
a { color: #004b87; text-decoration: underline; }
.kicker { font-size: 9pt; letter-spacing: 1.4pt; color: #004b87; border-bottom: 2pt solid #d78825; padding-bottom: 8pt; }
.reviewer { display: flex; gap: 22pt; font-size: 10pt; margin: 15pt 0 20pt; }
.reviewer span { border-bottom: .6pt solid #8a979f; flex: 1; padding: 4pt 0 9pt; }
.source { font-size: 8pt; color: #52616c; margin: 13pt 0; overflow-wrap: anywhere; }
.paper-note { border-left: 2pt solid #d78825; padding-left: 9pt; color: #465b68; font-size: 9pt; }
#review-decisions, #proposed-15-case-suite, #learning-probe-anchors-for-review, #prepared-implementation-and-next-checks { break-before: page; }
.notes { break-before: page; }
.notes h2 { margin-top: 0; }
.notes .line { height: 29pt; border-bottom: .5pt solid #b9c3ca; }
.screen-toolbar { display: flex; gap: 15px; align-items: center; background: #eaf2f7; padding: 14px; margin-bottom: 22px; }
button { border: 0; background: #0076a8; color: white; font: inherit; font-weight: 600; padding: 9px 14px; cursor: pointer; border-radius: 4px; }
button:focus-visible { outline: 3px solid #d78825; outline-offset: 3px; }
@media screen { body { max-width: 8.5in; margin: 25px auto; padding: .45in; background: white; box-shadow: 0 3px 30px #0001; } html { background: #edf2f6; } }
@media print { .screen-toolbar { display: none; } body { print-color-adjust: exact; -webkit-print-color-adjust: exact; } }
"""


def build(source, output):
    raw = source.read_bytes()
    content = render_markdown(raw.decode("utf-8"), source.resolve())
    fingerprint = hashlib.sha256(raw).hexdigest()
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Milestone 4 calibration review — printable packet</title><style>{STYLE}</style></head><body>
<div class="screen-toolbar"><button type="button" onclick="window.print()">Print / save as PDF</button><span>US Letter · portrait · page numbers in the supplied PDF</span></div>
<div class="kicker">INTERACTIVE MISSIONS / AUTHOR REVIEW</div>
<div class="reviewer"><span>Reviewer:</span><span>Date:</span></div>
{content}
<p class="source">Source: {html.escape(source.name)}<br>SHA-256: {fingerprint}</p>
<section class="notes"><h2>Written feedback</h2><p class="paper-note">Optional worksheet. Identify the example, case, or probe, then note your decision and reason. These handwritten notes are not applied automatically; return them to the agent or enter them in the dashboard.</p>
<p><strong>Decision:</strong> agree / revise / exclude case / discuss. For a revised evidence label, write pass, fail, or unknown.</p>
{''.join('<div class="line"></div>' for _ in range(17))}
</section></body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(f"Printable HTML: {output.resolve()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("design/mission-tutor-evaluation-calibration.md"))
    parser.add_argument("--output", type=Path, default=Path("build/evaluations/calibration-review/mission-tutor-evaluation-calibration.print.html"))
    args = parser.parse_args()
    build(args.source, args.output)


if __name__ == "__main__":
    main()
