import os

file_path = r'p:\ApolloSupport\frontend\src\api.ts'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = "if (typeof event.data !== 'string') {"
replacement = """if (event.data === 'pong') return; // Ignore pong
      
      if (typeof event.data !== 'string') {"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Target not found")
