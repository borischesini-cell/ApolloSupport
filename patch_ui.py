import os

def patch_app_tsx():
    file_path = r'p:\ApolloSupport\frontend\src\App.tsx'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target1 = "const [loginCreds, setLoginCreds] = useState({ username: '', password: '', domain: '.' });"
    replacement1 = "const [showLoginPassword, setShowLoginPassword] = useState(false);\n  const [loginCreds, setLoginCreds] = useState({ username: localStorage.getItem('last_remote_username') || '', password: '', domain: localStorage.getItem('last_remote_domain') || '.' });"
    
    if target1 in content and "showLoginPassword" not in content:
        content = content.replace(target1, replacement1)

    target2 = """                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 block">Contraseña</label>
                  <input
                    type="password"
                    value={loginCreds.password}
                    onChange={e => setLoginCreds(c => ({...c, password: e.target.value}))}
                    placeholder="••••••••"
                    onKeyDown={e => {
                      if (e.key === 'Enter' && loginCreds.username && loginCreds.password) {
                        setLoginLoading(true); setLoginError('');
                        sendViewerCommand({ type: 'login_session', ...loginCreds });
                      }
                    }}
                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50"
                  />
                </div>"""
    replacement2 = """                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 block">Contraseña</label>
                  <div className="relative">
                    <input
                      type={showLoginPassword ? "text" : "password"}
                      value={loginCreds.password}
                      onChange={e => setLoginCreds(c => ({...c, password: e.target.value}))}
                      placeholder="••••••••"
                      onKeyDown={e => {
                        if (e.key === 'Enter' && loginCreds.username && loginCreds.password) {
                          setLoginLoading(true); setLoginError('');
                          localStorage.setItem('last_remote_username', loginCreds.username);
                          localStorage.setItem('last_remote_domain', loginCreds.domain);
                          sendViewerCommand({ type: 'login_session', ...loginCreds });
                        }
                      }}
                      className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowLoginPassword(!showLoginPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white flex items-center justify-center"
                      title={showLoginPassword ? "Ocultar contraseña" : "Ver contraseña"}
                    >
                      {showLoginPassword ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" y1="2" x2="22" y2="22"/></svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                      )}
                    </button>
                  </div>
                </div>"""
                
    if target2 in content:
        content = content.replace(target2, replacement2)
    else:
        print("Target 2 not found!")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched App.tsx")

patch_app_tsx()
