import os

file_path = r'p:\ApolloSupport\frontend\src\App.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = "if (msg.type === 'telemetry') {"
replacement = "if (msg.type === 'telemetry') {\n      setSessionSwitching(false);"

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Target not found")
