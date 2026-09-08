"""Emit corrected per-run security values + significance, for the erratum."""
import json, subprocess, tempfile, csv
from collections import defaultdict
from pathlib import Path
from scipy import stats

root = Path("data/raw/raw")
def is_test(rel):
    n = rel.rsplit("/",1)[-1]
    return (n.startswith("test_") or n.endswith("_test.py") or n=="conftest.py"
            or "/tests/" in f"/{rel}" or rel.startswith("tests/"))

per = defaultdict(lambda: {"old":[], "new":[]})
out = []
for run in sorted(root.iterdir()):
    if not (run.is_dir() and run.name.startswith("main_001__")): continue
    _, spec, cond, rep = run.name.split("__")
    cb = next((d/"codebase.json" for d in run.iterdir() if (d/"codebase.json").is_file()), None)
    if cb is None: continue
    files = json.loads(cb.read_text()).get("files", {})
    with tempfile.TemporaryDirectory() as tmp:
        scan = Path(tmp)/"code"; scan.mkdir(); loc=0
        for rel, c in files.items():
            if not rel.endswith(".py"): continue
            t=scan/rel; t.parent.mkdir(parents=True, exist_ok=True); t.write_text(c); loc+=len(c.splitlines())
        loc = loc or 1
        cwe=kept=[]
        if any(scan.rglob("*.py")):
            p=subprocess.run(["bandit","-r",str(scan),"-f","json","-q"],capture_output=True,text=True,check=False)
            try: res=json.loads(p.stdout).get("results",[]) if p.stdout.strip() else []
            except json.JSONDecodeError: res=[]
            cwe=[r for r in res if (r.get("issue_cwe") or {}).get("id")]
            kept=[r for r in cwe if not (r.get("test_id")=="B101"
                  and is_test(str(Path(r["filename"]).relative_to(scan)).replace("\\","/")))]
    o,n = len(cwe)/loc*1000, len(kept)/loc*1000
    per[cond]["old"].append(o); per[cond]["new"].append(n)
    out.append({"condition":cond,"spec_name":spec,"rep":rep,
                "security_density_published":round(o,4),
                "security_density_corrected":round(n,4)})

Path("data/reports/security_density_corrected.csv").write_text("")
with open("data/reports/security_density_corrected.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

conds=["claude_code","cursor_agent","replit_agent","antigravity"]
print("Kruskal-Wallis on security_density, four conditions:\n")
for key,label in (("old","as published"),("new","corrected")):
    groups=[per[c][key] for c in conds]
    H,p = stats.kruskal(*groups)
    print(f"  {label:<13} H={H:7.2f}  p={p:.3e}")
print()
print("claude_code vs cursor_agent (the two live conditions):")
for key,label in (("old","as published"),("new","corrected")):
    U,p = stats.mannwhitneyu(per['claude_code'][key], per['cursor_agent'][key], alternative='two-sided')
    a=sum(per['claude_code'][key])/30; b=sum(per['cursor_agent'][key])/30
    print(f"  {label:<13} U={U:7.1f}  p={p:.4f}   claude {a:6.2f}  cursor {b:6.2f}")
print("\nwrote data/reports/security_density_corrected.csv")
