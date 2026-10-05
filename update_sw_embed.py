import re
import base64
import textwrap
from pathlib import Path

sw = Path(r"X:\WEB_PRESALE\Source\sw_presale.js").read_bytes()
b64 = base64.b64encode(sw).decode("ascii")
chunks = textwrap.wrap(b64, 76)
lines = ["Function SwJsEmbedded()", '   Local cBase64 := ""']
for chunk in chunks:
    lines.append('   cBase64 += "' + chunk + '"')
lines.append("Return hb_base64Decode( cBase64 )")
embed_text = "\n".join(lines)

html_path = Path(r"X:\WEB_PRESALE\Source\HtmlApp.prg")
text = html_path.read_text(encoding="utf-8")
pat = r"Function SwJsEmbedded\(\).*?Return hb_base64Decode\( cBase64 \)"
m = re.search(pat, text, re.S)
if not m:
    raise SystemExit("SwJsEmbedded block not found")
text = text[: m.start()] + embed_text + text[m.end() :]
html_path.write_text(text, encoding="utf-8")
print("SwJsEmbedded updated, bytes:", len(sw))
