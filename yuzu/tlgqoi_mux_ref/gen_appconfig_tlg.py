"""Parse TLGref .tlg files in the current directory and generate appconfig.tjs."""
import os
import struct

MAGIC = b"TLGref\x00raw\x1a"
FNAME_OFFSET = 0x2c


def parse_tlgref(path):
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(MAGIC):
        return None
    raw = data[FNAME_OFFSET:]
    chars = []
    for i in range(0, len(raw) - 1, 2):
        code = struct.unpack_from("<H", raw, i)[0]
        if code == 0:
            break
        chars.append(chr(code))
    return "".join(chars)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    refs = []
    for name in sorted(os.listdir(script_dir)):
        if not name.lower().endswith(".tlg"):
            continue
        ref = parse_tlgref(os.path.join(script_dir, name))
        if ref is not None:
            refs.append(ref)

    if not refs:
        print("No TLGref files found.")
        return

    lines = []
    lines.append("// Kirikiri Batch Dumper Script (with .sinfo support)")
    lines.append(f"// Generated from {len(refs)} file(s).")
    lines.append("")
    for ref in refs:
        lines.append(f'try {{ Scripts.evalStorage("{ref}"); }} catch {{}}')
    lines.append("")
    lines.append("System.exit();")
    lines.append("")

    out_path = os.path.join(script_dir, "appconfig.tjs")
    with open(out_path, "wb") as f:
        f.write(b"\xff\xfe")  # UTF-16LE BOM
        f.write("\r\n".join(lines).encode("utf-16-le"))

    print(f"Generated appconfig.tjs with {len(refs)} entry(ies):")
    for ref in refs:
        print(f"  {ref}")


if __name__ == "__main__":
    main()
