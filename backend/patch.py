import os

file_path = r'p:\ApolloSupport\backend\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = 'docs_url="/documentacion"\n)'
replacement = 'docs_url="/documentacion"\n)\n\nimport backup_routes\napp.include_router(backup_routes.router, prefix="/api")'

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Target not found")
