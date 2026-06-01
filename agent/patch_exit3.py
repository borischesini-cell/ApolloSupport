import os

file_path = r'p:\ApolloSupport\agent\centinela.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = 'import os; os._exit(0)'
replacement = """if HQ_FFMPEG_PROC is not None:
                                            try: HQ_FFMPEG_PROC.terminate()
                                            except: pass
                                        import os; os._exit(0)"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Target not found")
