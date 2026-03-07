"""Parse cglist.csv and generate appconfig.tjs."""
import os


def parse_cglist(path):
    """Parse cglist.csv (UTF-16LE with BOM) and return list of name.tlg entries."""
    with open(path, "rb") as f:
        data = f.read()
    text = data[2:].decode("utf-16-le")
    names = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(":"):
            continue
        parts = [p.strip() for p in line.split(",")]
        for part in parts:
            if not part:
                continue
            # Handle composite entries like "ev408ab|*ev408ba"
            for sub in part.split("|*"):
                sub = sub.strip()
                if sub:
                    names.append(sub + ".tlg")
    return names


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cglist_path = os.path.join(script_dir, "cglist.csv")

    if not os.path.exists(cglist_path):
        print("cglist.csv not found.")
        return

    entries = parse_cglist(cglist_path)
    if not entries:
        print("No entries found in cglist.csv.")
        return

    # Deduplicate while preserving order (case-insensitive)
    seen = set()
    unique = []
    for e in entries:
        key = e.lower()
        if key not in seen:
            seen.add(key)
            unique.append(e)

    lines = []
    lines.append("// Kirikiri Batch Dumper Script (with .sinfo support)")
    lines.append(f"// Generated from {len(unique)} file(s).")
    lines.append("")
    for entry in unique:
        lines.append(f'try {{ Scripts.evalStorage("{entry}"); }} catch {{}}')
    lines.append("")
    lines.append("System.exit();")
    lines.append("")

    out_path = os.path.join(script_dir, "appconfig.tjs")
    with open(out_path, "wb") as f:
        f.write(b"\xff\xfe")  # UTF-16LE BOM
        f.write("\r\n".join(lines).encode("utf-16-le"))

    print(f"Generated appconfig.tjs with {len(unique)} entries from cglist.csv.")


if __name__ == "__main__":
    main()
