#!/usr/bin/env python3
import re
import subprocess

from environment import paths

# Upgrade do uv.lock
subprocess.run(["uv", "sync", "--upgrade"], cwd=paths.BASE_DIR)

# Pega versões resolvidas
result = subprocess.run(["uv", "tree", "-d", "1"], cwd=paths.BASE_DIR, capture_output=True, text=True)

lines = result.stdout.strip().split("\n")[1:]
deps = []

for line in lines:
    match = re.search(r"([a-zA-Z0-9\-._\[\]]+)\s+v([\d.]+)", line)
    if match:
        name, version = match.groups()
        deps.append(f'    "{name}>={version}",')

print("dependencies = [")
for dep in deps:
    print(dep)
print("]")
