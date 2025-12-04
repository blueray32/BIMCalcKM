file_path = "/opt/bimcalc/docker-compose.yml"

with open(file_path, "r") as f:
    content = f.read()

# Fix the double command issue manually since yaml parser might fail on invalid yaml
lines = content.split("\n")
new_lines = []
app_section = False
worker_section = False

for line in lines:
    stripped = line.strip()
    if stripped == "app:":
        app_section = True
        worker_section = False
        new_lines.append(line)
        continue
    if stripped == "worker:":
        app_section = False
        worker_section = True
        new_lines.append(line)
        continue

    if app_section and stripped.startswith("command:"):
        # Replace any command in app section with tail -f /dev/null
        # But only add it once
        if not any(
            "tail -f /dev/null" in line for line in new_lines[-5:]
        ):  # Check if we just added it
            # Preserve indentation
            indent = line[: line.find("command:")]
            new_lines.append(f"{indent}command: tail -f /dev/null")
    elif worker_section and stripped.startswith("command:"):
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_path, "w") as f:
    f.write("\n".join(new_lines))

print("Fixed docker-compose.yml")
