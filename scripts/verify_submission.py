"""Pre-submission verification. Every check is a fact about the repo."""
import csv, json, re, subprocess
from pathlib import Path

ROOT = Path(".")
D = ROOT / "docs/dissertation/DISSERTATION_FULL.md"
s = D.read_text()
fails, warns = [], []

def check(cond, msg):
    (print(f"  ok    {msg}") if cond else (fails.append(msg), print(f"  FAIL  {msg}")))

def warn(cond, msg):
    (print(f"  ok    {msg}") if cond else (warns.append(msg), print(f"  warn  {msg}")))

print("\n[1] FIGURES")
refs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', s)
check(len(refs) == 13, f"13 figures referenced (found {len(refs)})")
for r in refs:
    check((ROOT / "docs/dissertation" / r).resolve().exists(), f"file exists: {r}")
caps = re.findall(r'^\*\*Figure ([0-9.]+)\*\*', s, re.M)
check(caps == sorted(caps, key=lambda x: [int(p) for p in x.split(".")]),
      f"captions in ascending order: {caps}")
lof = re.findall(r'^- Figure ([0-9.]+)', s, re.M)
check(set(lof) == set(caps), "List of Figures matches captions")

print("\n[2] TABLES")
tcaps = re.findall(r'^\*\*Table ([0-9.]+)\*\*', s, re.M)
check(len(tcaps) == len(set(tcaps)), f"no duplicate table numbers: {tcaps}")
lot = re.findall(r'^- Table ([0-9.]+)', s, re.M)
check(set(lot) <= set(tcaps) or set(tcaps) <= set(lot),
      f"List of Tables consistent (list={sorted(set(lot))}, captions={sorted(set(tcaps))})")

print("\n[3] NUMBERS AGREE WITH THE DATA")
import statistics as st
rows = list(csv.DictReader(open(ROOT / "data/reports/main_001.csv")))
def mean(metric, cond):
    v = [float(r["value"]) for r in rows
         if r["metric"] == metric and r["run_id"].split("__")[2] == cond]
    return sum(v) / len(v)
for cond, want in [("claude_code", "0.00"), ("cursor_agent", "0.17"),
                   ("replit_agent", "1.33"), ("antigravity", "0.33")]:
    m = mean("hallucinations", cond)
    check(f"{m:.2f}" == want, f"Table 4.1 hallucinations {cond} = {want} (data: {m:.2f})")
sec = list(csv.DictReader(open(ROOT / "data/reports/security_density_corrected.csv")))
for cond, want in [("claude_code", "9.65"), ("cursor_agent", "5.93"),
                   ("replit_agent", "0.00"), ("antigravity", "1.47")]:
    v = [float(r["security_density_corrected"]) for r in sec if r["condition"] == cond]
    m = sum(v) / len(v)
    check(f"{m:.2f}" == want, f"Table 4.1 security {cond} = {want} (data: {m:.2f})")
    check(f"| {want} |" in s or f"({want})" in s, f"  {want} appears in the document")

print("\n[4] NO STALE CLAIMS")
stale = {
    "pre-erratum security 42.05 in a table": "| 42.05 |",
    "pre-erratum security 43.67 in a table": "| 43.67 |",
    "withdrawn interaction called significant": "significant condition-by-spec interaction",
    "kappa described as planned": "planned step",
    "Replit drift 'entirely' in CLI": "concentrated entirely in the CLI",
    "old hallucination range": "0.00 to 1.00 hallucinations",
    "old name": "Dominic Orume Uririe",
    "old degree title": "MSc Artificial Intelligence —",
}
for msg, needle in stale.items():
    check(needle not in s, f"absent: {msg}")

print("\n[4b] PUNCTUATION")
check(s.count(chr(8212)) == 0,
      f"no em dashes ({s.count(chr(8212))} found) — a recognised marker of machine prose")
check(s.count(chr(8211)) > 0,
      "en dashes retained for ranges and compound names")
import re as _re
_flat = " ".join(s.split())
_d = _m = 0
for _c in _flat:
    if _c == "(": _d += 1; _m = max(_m, _d)
    elif _c == ")": _d = max(0, _d - 1)
check(_m <= 2, f"parenthesis nesting never exceeds two deep (max {_m})")
for _n, _p in [("doubled spaces before brackets", r"\s\s+\("),
               ("doubled commas", r",\s*,"),
               ("space before punctuation", r"\s+[,.;:](?![0-9])")]:
    check(not _re.search(_p, _flat), f"no {_n}")

print("\n[5] KAPPA REPORTED CORRECTLY")
kr = json.loads((ROOT / "data/labels/kappa_results.json").read_text())
check("0.870" in s and "0.853" in s and "0.727" in s, "pre-registered kappa values present")
check("circular" in s, "circularity of post-repair kappa declared")
# 1.000 is legitimate only inside the passage that disclaims it
bad = [ln for ln in s.splitlines() if "1.000" in ln
       and not ln.startswith(">")          # editorial notes never ship
       and "raises κ" not in ln]
check(not bad, f"post-repair kappa appears only in its disclaimer ({len(bad)} stray)")

print("\n[6] IDENTITY")
check("**Author: Uririe, Orume Dominic**" in s, "author name as verified")
check("MSc Artificial Intelligence and Business Strategy" in s, "programme title as verified")

print("\n[7] REFERENCES")
refsec = s.split("# References")[-1] if "# References" in s else ""
n_refs = len(re.findall(r"^[A-Z][A-Za-z\-']+,\s", refsec, re.M))
check(n_refs >= 20, f"reference list populated ({n_refs} entries)")
cited = set(re.findall(r"\(([A-Z][A-Za-z\-']+)(?:\s+et al\.)?,\s*\d{4}", s))
missing = sorted(a for a in cited if a not in refsec)
warn(not missing, f"every in-text author appears in the reference list (missing: {missing})")

print("\n[8] WORD COUNT")
lines = s.splitlines()
cut = next(i for i, l in enumerate(lines) if re.match(r"^#+\s*References", l, re.I))
body = [l for l in lines[:cut] if not l.startswith(">")]
ch1 = next(i for i, l in enumerate(body) if l.startswith("## 1.1"))
ch = body[ch1:]
out, skip = [], False
for l in ch:
    if l.startswith("**Figure "): skip = True
    elif skip and l.strip() == "": skip = False
    if not skip and not l.startswith("!["): out.append(l)
w = lambda ls: len(re.findall(r"\S+", "\n".join(ls)))
print(f"        chapters incl captions: {w(ch)}   excl captions: {w(out)}")
check(w(out) <= 12000, f"under 12,000 excluding captions ({w(out)})")

print("\n[9] REPO HYGIENE")
r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
check(not r.stdout.strip(), "working tree clean")
# chapter files are generated; they are stale only if they differ from the master
import subprocess as _sp
_sp.run([".venv/bin/python", "scripts/split_chapters.py"], capture_output=True)
r2 = _sp.run(["git", "status", "--porcelain", "docs/dissertation"],
             capture_output=True, text=True)
check(not r2.stdout.strip(), "chapter extracts are in sync with the master")
check("Generated file" in (ROOT / "docs/dissertation/CHAPTER_4_RESULTS.md").read_text(),
      "chapter extracts carry the generated-file banner")

print(f"\n{'='*56}\n  {len(fails)} failures, {len(warns)} warnings")
for f in fails: print("   FAIL:", f)
for f in warns: print("   warn:", f)
