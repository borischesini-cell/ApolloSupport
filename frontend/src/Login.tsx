import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Lock, Eye, EyeOff, User, Trash2, ChevronDown, ChevronUp, Download } from 'lucide-react';
import { API_URL } from './api';

interface SavedUser {
    email: string;
    nombre: string;
    password?: string;
}

export default function Login({
  onLogin,
  onOpenCentinelaInstall,
}: {
  onLogin: () => void;
  onOpenCentinelaInstall?: () => void;
}) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [rememberMe, setRememberMe] = useState(true);
    const [savedUsers, setSavedUsers] = useState<SavedUser[]>([]);
    const [systemUsers, setSystemUsers] = useState<SavedUser[]>([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [highlightedIndex, setHighlightedIndex] = useState(-1);
    const suggestionRefs = useRef<(HTMLButtonElement | null)[]>([]);

    useEffect(() => {
        try {
            const saved = localStorage.getItem('saved_users');
            if (saved) {
                const parsed = JSON.parse(saved);
                if (Array.isArray(parsed)) {
                    setSavedUsers(parsed);
                    return;
                }
            }
        } catch (err) {
            console.error("Error reading saved_users from localStorage:", err);
        }

        // Si falla, está corrupto o vacío, inyectamos los valores por defecto
        const defaults: SavedUser[] = [
            { email: 'admin@masteris.com', nombre: 'Juan Administrador' },
            { email: 'dev@masteris.com', nombre: 'María Programadora' }
        ];
        try {
            localStorage.setItem('saved_users', JSON.stringify(defaults));
        } catch (e) {
            console.error("Error writing default saved_users to localStorage:", e);
        }
        setSavedUsers(defaults);
    }, []);

    // Cargar usuarios del sistema para autocompletado en Combobox
    useEffect(() => {
        fetch(`${API_URL}/public/users`)
            .then(res => {
                if (res.ok) return res.json();
                throw new Error("No se pudo obtener la lista de usuarios del sistema");
            })
            .then(data => {
                if (Array.isArray(data)) {
                    setSystemUsers(data);
                }
            })
            .catch(err => {
                console.error("Error cargando usuarios públicos del backend:", err);
            });
    }, []);

    // Combinamos usuarios del sistema (DB) y locales (savedUsers), priorizando DB y conservando claves guardadas
    const allAvailableUsers = useMemo(() => {
        const merged: Record<string, SavedUser> = {};
        
        // Primero agregamos los de la base de datos (públicos)
        systemUsers.forEach(u => {
            merged[u.email.toLowerCase()] = {
                email: u.email,
                nombre: u.nombre
            };
        });
        
        // Luego agregamos o completamos con los locales (que contienen contraseñas de sesión anterior)
        if (Array.isArray(savedUsers)) {
            savedUsers.forEach(u => {
                const lowerEmail = u.email.toLowerCase();
                if (merged[lowerEmail]) {
                    merged[lowerEmail].password = u.password;
                    merged[lowerEmail].nombre = u.nombre || merged[lowerEmail].nombre;
                } else {
                    merged[lowerEmail] = u;
                }
            });
        }
        
        return Object.values(merged);
    }, [systemUsers, savedUsers]);

    // Filtrar sugerencias en base a lo que se tipea en el email
    const suggestions = useMemo(() => {
        const query = email.trim().toLowerCase();
        if (!query) {
            // Si está vacío pero enfocado, mostramos todos los disponibles como sugerencia inicial
            return allAvailableUsers;
        }
        return allAvailableUsers.filter(u => 
            u.email.toLowerCase().includes(query) || 
            u.nombre.toLowerCase().includes(query)
        );
    }, [email, allAvailableUsers]);

    // Resetear el índice resaltado cuando cambia el email
    useEffect(() => {
        setHighlightedIndex(-1);
    }, [email]);

    // Asegurar que el elemento resaltado esté siempre visible al navegar con el teclado
    useEffect(() => {
        if (highlightedIndex >= 0 && suggestionRefs.current[highlightedIndex]) {
            suggestionRefs.current[highlightedIndex]?.scrollIntoView({
                block: 'nearest',
            });
        }
    }, [highlightedIndex]);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (!showSuggestions) {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                setShowSuggestions(true);
                e.preventDefault();
            }
            return;
        }

        if (suggestions.length === 0) return;

        if (e.key === 'ArrowDown') {
            setHighlightedIndex((prev) => (prev + 1) % suggestions.length);
            e.preventDefault();
        } else if (e.key === 'ArrowUp') {
            setHighlightedIndex((prev) => (prev - 1 + suggestions.length) % suggestions.length);
            e.preventDefault();
        } else if (e.key === 'Enter') {
            if (highlightedIndex >= 0 && highlightedIndex < suggestions.length) {
                handleSelectUser(suggestions[highlightedIndex]);
                e.preventDefault();
            }
        } else if (e.key === 'Escape') {
            setShowSuggestions(false);
            setHighlightedIndex(-1);
            e.preventDefault();
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        console.log("Intentando login en:", `${API_URL}/token`);

        try {
            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);

            const res = await fetch(`${API_URL}/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData,
            });

            console.log("Respuesta login:", res.status);

            if (!res.ok) {
                const errData = await res.json().catch(() => ({ detail: 'Error de credenciales.' }));
                throw new Error(errData.detail || 'Email o contraseña incorrectos.');
            }

            const data = await res.json();
            console.log("Login exitoso, recibiendo usuario:", data.usuario?.nombre);

            // Memorizar usuario si rememberMe está activo (solo correo y nombre)
            if (rememberMe) {
                const currentSaved = Array.isArray(savedUsers) ? savedUsers : [];
                const updated = [...currentSaved];
                const index = updated.findIndex(u => u.email === email);
                const userObj: SavedUser = {
                    email: email,
                    nombre: data.usuario?.nombre || email.split('@')[0]
                };
                if (index > -1) {
                    updated[index] = userObj;
                } else {
                    updated.push(userObj);
                }
                localStorage.setItem('saved_users', JSON.stringify(updated));
                setSavedUsers(updated);
            }

            localStorage.setItem('token', data.access_token);
            localStorage.setItem('user', JSON.stringify(data.usuario));

            onLogin();
        } catch (err: any) {
            console.error("Error en login:", err);
            setError(err.message || 'Error al conectar de forma segura.');
        } finally {
            setLoading(false);
        }
    };

    const handleSelectUser = (u: SavedUser) => {
        setEmail(u.email);
        setPassword(u.password || '');
        setShowSuggestions(false);
        setHighlightedIndex(-1);
    };

    const handleDeleteSavedUser = (e: React.MouseEvent, emailToDelete: string) => {
        e.stopPropagation();
        const currentSaved = Array.isArray(savedUsers) ? savedUsers : [];
        const filtered = currentSaved.filter(u => u.email !== emailToDelete);
        localStorage.setItem('saved_users', JSON.stringify(filtered));
        setSavedUsers(filtered);
        if (email === emailToDelete) {
            setEmail('');
            setPassword('');
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-[#0a0f1a] bg-[url('https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=2070&auto=format&fit=crop')] bg-cover bg-center">
            <div className="absolute inset-0 bg-[#0a0f1a]/85 backdrop-blur-md"></div>

            <div className="relative z-10 w-full max-w-[340px] px-6 pt-7 pb-6 rounded-3xl bg-[#1e293b]/60 backdrop-blur-xl border border-white/10 shadow-2xl animate-in zoom-in-95 duration-500">
                <div className="text-center mb-5">
                    <div className="w-14 h-14 mx-auto bg-gradient-to-br from-brand-400 to-orange-600 rounded-2xl flex items-center justify-center shadow-lg shadow-brand-500/40 mb-4">
                        <Lock className="text-white" size={28} />
                    </div>
                    <h2 className="text-2xl font-extrabold tracking-tight">
                        <span className="text-white">Apollo</span>
                        <span className="text-brand-500">Support</span>
                    </h2>
                    <p className="text-slate-400 font-medium mt-1.5 text-sm">Autenticación Segura (Master IS)</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5 pt-3">
                    {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/50 text-red-500 text-sm font-bold text-center animate-in slide-in-from-top-2">{error}</div>}

                    {/* Correo Electrónico Oficial con Autocompletado / Combobox premium */}
                    <div className="relative pt-1">
                        <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2.5">Correo Electrónico Oficial</label>
                        <div className="relative">
                            <input
                                type="email" required
                                value={email} 
                                onChange={(e) => {
                                    setEmail(e.target.value);
                                    setShowSuggestions(true);
                                }}
                                onFocus={() => setShowSuggestions(true)}
                                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                                onKeyDown={handleKeyDown}
                                aria-autocomplete="list"
                                aria-expanded={showSuggestions}
                                aria-controls="suggestions-list"
                                role="combobox"
                                className="w-full bg-slate-900/50 border border-slate-700 text-white rounded-xl px-3 py-3.5 pr-16 leading-5 focus:outline-none focus:ring-2 focus:ring-brand-500 transition-all placeholder:text-slate-500 text-sm"
                                placeholder="ej: soporte@masteris.com"
                                autoComplete="off"
                            />
                            <button
                                type="button"
                                onClick={(e) => {
                                    e.preventDefault();
                                    setShowSuggestions(prev => !prev);
                                }}
                                onMouseDown={(e) => {
                                    // Evitar que el input pierda foco y se cierre la lista al hacer click
                                    e.preventDefault();
                                }}
                                className="absolute right-10 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors cursor-pointer"
                                aria-label="Toggle suggestions"
                            >
                                {showSuggestions ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                            </button>
                            <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">
                                <User size={18} />
                            </div>
                        </div>

                        {/* Listado de sugerencias de Combobox premium */}
                        {showSuggestions && suggestions.length > 0 && (
                            <div 
                                id="suggestions-list"
                                role="listbox"
                                className="absolute z-20 w-full mt-1.5 max-h-60 overflow-y-auto bg-slate-950/95 backdrop-blur-xl border border-slate-700/60 rounded-xl shadow-2xl divide-y divide-slate-800 animate-in fade-in slide-in-from-top-1 duration-150 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent"
                            >
                                {suggestions.map((u, idx) => {
                                    const isHighlighted = idx === highlightedIndex;
                                    return (
                                        <button
                                            key={u.email}
                                            type="button"
                                            ref={(el) => { suggestionRefs.current[idx] = el; }}
                                            onMouseDown={() => handleSelectUser(u)}
                                            onMouseEnter={() => setHighlightedIndex(idx)}
                                            role="option"
                                            aria-selected={isHighlighted}
                                            className={`w-full text-left p-3 flex items-center gap-3 transition-all cursor-pointer group border-l-4 ${
                                                isHighlighted 
                                                    ? 'bg-brand-500/20 text-white border-brand-500' 
                                                    : 'hover:bg-brand-500/10 text-slate-300 border-transparent'
                                            }`}
                                        >
                                            <div className={`w-8 h-8 rounded-full bg-gradient-to-br from-brand-400/20 to-orange-500/20 flex items-center justify-center border border-brand-500/30 text-brand-400 font-bold text-xs transition-transform ${
                                                isHighlighted ? 'scale-110' : 'group-hover:scale-105'
                                            }`}>
                                                {u.nombre.charAt(0).toUpperCase()}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className={`text-sm font-bold truncate ${
                                                    isHighlighted ? 'text-white' : 'text-slate-200 group-hover:text-white'
                                                }`}>{u.nombre}</p>
                                                <p className={`text-xs truncate ${
                                                    isHighlighted ? 'text-slate-200' : 'text-slate-400 group-hover:text-slate-300'
                                                }`}>{u.email}</p>
                                            </div>
                                            {u.email && (
                                                <span className={`text-[10px] font-extrabold px-2.5 py-0.5 rounded-lg whitespace-nowrap border ${
                                                    isHighlighted 
                                                        ? 'text-white bg-brand-500/40 border-brand-400' 
                                                        : 'text-brand-400 bg-brand-500/10 border-brand-500/20'
                                                }`}>
                                                    Cuenta Recordada
                                                </span>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2.5">Contraseña de Agente</label>
                        <div className="relative">
                            <input
                                type={showPassword ? "text" : "password"} required
                                value={password} onChange={(e) => setPassword(e.target.value)}
                                className="w-full bg-slate-900/50 border border-slate-700 text-white rounded-xl px-3 py-3.5 pr-11 leading-5 focus:outline-none focus:ring-2 focus:ring-brand-500 transition-all placeholder:text-slate-500 text-sm"
                                placeholder="••••••••"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors"
                            >
                                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                            </button>
                        </div>
                    </div>

                    {/* Recordar Cuenta checkbox */}
                    <div className="flex items-center justify-between pt-1 font-sans">
                        <label className="flex items-center gap-2 text-xs font-semibold text-slate-400 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={rememberMe}
                                onChange={(e) => setRememberMe(e.target.checked)}
                                className="w-4 h-4 rounded bg-slate-900 border-slate-700 accent-brand-500 cursor-pointer"
                            />
                            Recordar mi cuenta (solo correo)
                        </label>
                        
                        {email && Array.isArray(savedUsers) && savedUsers.some(u => u.email === email) && (
                            <button
                                type="button"
                                onClick={(e) => handleDeleteSavedUser(e, email)}
                                className="text-xs text-red-400 hover:text-red-300 transition-colors flex items-center gap-1 font-bold"
                                title="Olvidar esta cuenta"
                            >
                                <Trash2 size={13} /> Olvidar cuenta
                            </button>
                        )}
                    </div>

                    <button
                        type="submit" disabled={loading}
                        className="w-full bg-gradient-to-r from-brand-500 to-orange-600 hover:from-brand-600 hover:to-orange-700 text-white font-extrabold py-3.5 rounded-xl shadow-[0_0_20px_rgba(245,158,11,0.4)] transition-all transform hover:-translate-y-1 mt-2 disabled:opacity-50 disabled:hover:translate-y-0 tracking-wide text-sm"
                    >
                        {loading ? 'Verificando seguridad...' : 'INGRESAR'}
                    </button>

                    {onOpenCentinelaInstall && (
                        <button
                            type="button"
                            onClick={onOpenCentinelaInstall}
                            className="w-full mt-3 flex items-center justify-center gap-2 py-3 rounded-xl border border-white/10 bg-slate-900/60 hover:bg-slate-800 text-slate-200 text-xs font-bold transition-all"
                        >
                            <Download size={15} className="text-brand-400" />
                            Instalar / Actualizar Centinela
                        </button>
                    )}
                </form>
            </div>
        </div>
    );
}
