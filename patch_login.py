import os

def patch_app_tsx():
    file_path = r'p:\ApolloSupport\frontend\src\App.tsx'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target1 = "const [loginCreds, setLoginCreds] = useState({"
    replacement1 = "const [showLoginPassword, setShowLoginPassword] = useState(false);\n  const [loginCreds, setLoginCreds] = useState({"
    
    if target1 in content and "showLoginPassword" not in content:
        content = content.replace(target1, replacement1)

    target2 = """                  <input
                    type="password"
                    value={loginCreds.password}"""
    replacement2 = """                  <div className="relative">
                  <input
                    type={showLoginPassword ? "text" : "password"}
                    value={loginCreds.password}"""
    
    if target2 in content:
        content = content.replace(target2, replacement2)

    target3 = """                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50"
                  />
                </div>"""
    replacement3 = """                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowLoginPassword(!showLoginPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                    title={showLoginPassword ? "Ocultar" : "Mostrar"}
                  >
                    {showLoginPassword ? "👁️‍🗨️" : "👁️"}
                  </button>
                  </div>
                </div>"""
                
    if target3 in content:
        content = content.replace(target3, replacement3)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched App.tsx")

def patch_centinela():
    file_path = r'p:\ApolloSupport\agent\centinela.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # We use regex to match because of encoding/unicode variations in comments
    import re
    pattern = re.compile(
        r'elif data\.get\("type"\) == "switch_session":.*?target_id = int\(data\.get\("session_id", 1\)\).*?cur_id = get_current_session_id\(\).*?if target_id == cur_id:.*?else:.*?ok = request_session_switch\(target_id\)',
        re.DOTALL
    )
    
    replacement = """elif data.get("type") in ("switch_session", "login_session"):
                                # Técnico quiere cambiar a otra sesión Windows o iniciar sesión
                                target_id = int(data.get("session_id", 1))
                                username = data.get("username", "")
                                password = data.get("password", "")
                                cur_id = get_current_session_id()
                                if target_id == cur_id and not username:
                                    logger.info("[SESSION] Ya estamos en sesión %d", target_id)
                                else:
                                    logger.info("[SESSION] Switch/Login a sesión %d (login=%r)", target_id, bool(username))
                                    ok = request_session_switch(target_id, username, password)"""

    if pattern.search(content):
        content = pattern.sub(replacement, content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched centinela.py")
    else:
        print("Could not find pattern in centinela.py")

patch_app_tsx()
patch_centinela()
