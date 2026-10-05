import re
import base64
import textwrap
from pathlib import Path

html_path = Path(r"X:\WEB_PRESALE\Source\HtmlApp.prg")
sw_path = Path(r"X:\WEB_PRESALE\Source\sw_presale.js")

sw = sw_path.read_bytes()
b64 = base64.b64encode(sw).decode("ascii")
chunks = textwrap.wrap(b64, 76)
lines = ["Function SwJsEmbedded()", '   Local cBase64 := ""']
for chunk in chunks:
    lines.append('   cBase64 += "' + chunk + '"')
lines.append("Return hb_base64Decode( cBase64 )")
embed = "\n".join(lines)

text = html_path.read_text(encoding="utf-8")
text = text.replace("_SwJsEmbedded()", "SwJsEmbedded()")

if "Function SwJsEmbedded()" not in text:
    marker = "Return cJs\nFunction Serve_leaflet_js()"
    if marker not in text:
        raise SystemExit("marker not found")
    text = text.replace(marker, "Return cJs\n\n" + embed + "\n\nFunction Serve_leaflet_js()", 1)
    print("inserted SwJsEmbedded")
else:
    text = re.sub(
        r"Function SwJsEmbedded\(\).*?Return hb_base64Decode\( cBase64 \)",
        embed,
        text,
        count=1,
        flags=re.S,
    )
    print("replaced SwJsEmbedded")

html_path.write_text(text, encoding="utf-8")
print("done, sw bytes:", len(sw))
