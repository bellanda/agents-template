import re
import subprocess

from config import paths

# Upgrade do uv.lock
subprocess.run(["uv", "sync", "--upgrade"], cwd=paths.BASE_DIR)

lines_pattern = re.compile(r"([a-zA-Z0-9\-._\[\]]+)\s+v([\d.]+)")
final_deps_pattern = re.compile(r"dependencies = \[[\s\S]*?\n\]")

# Pega versões resolvidas
result = subprocess.run(["uv", "tree", "-d", "1"], cwd=paths.BASE_DIR, capture_output=True, text=True)

lines = result.stdout.strip().split("\n")[1:]
deps = []

for line in lines:
    match = lines_pattern.search(line)
    if match:
        name, version = match.groups()
        deps.append(f'    "{name}>={version}",')

final_deps = ""
final_deps += "dependencies = [\n"
for dep in deps:
    final_deps += dep + "\n"
final_deps += "]"

with open(paths.BASE_DIR / "pyproject.toml", "r", encoding="utf-8") as f:
    content = f.read()
    content = final_deps_pattern.sub(final_deps, content)

with open(paths.BASE_DIR / "pyproject.toml", "w", encoding="utf-8") as f:
    f.write(content)
