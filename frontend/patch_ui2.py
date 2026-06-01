import os

file_path = r'p:\ApolloSupport\frontend\src\App.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target1 = "setSessionSwitching(true);"
replacement1 = "setSessionSwitching(true); setTimeout(() => setSessionSwitching(false), 15000);"

if target1 in content:
    content = content.replace(target1, replacement1)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched App.tsx successfully")
else:
    print("Target not found")
