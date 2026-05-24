import re

file_path = r'p:\ApolloSupport\frontend\src\App.tsx'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove MSE refs
content = re.sub(
    r'// Refs para MSE \(no causan re-renders\).*?const lastSeekTimeRef = useRef<number>\(0\);',
    '// Refs eliminados para MSE (usando MJPEG nativo)',
    content,
    flags=re.DOTALL
)

# 2. Remove useEffect for MSE initialization down to useHqViewerWebSocket call
content = re.sub(
    r'// Inicializar/destruir MSE cuando se activa HQ o cambia el modo fullscreen\s+useEffect\(\(\) => \{.*?(?:logCallback:\s*logFrontendToBackend,\s*\}\);)',
    '// MSE and useHqViewerWebSocket have been removed in favor of MJPEG Turbo\n  // via the standard viewer websocket.',
    content,
    flags=re.DOTALL
)

# 3. Modify toggleHqMode
toggle_old = """  const toggleHqMode = () => {
    const next = !hqEnabled;
    setHqEnabled(next);
    if (hqStorageKey) localStorage.setItem(hqStorageKey, String(next));
    if (!next) {
      // Al desactivar: limpiar MSE
      mseReadyRef.current = false;
      sourceBufferRef.current = null;
      chunkQueueRef.current = [];
      setHqState('off');
      setWsViewerConnected(false);
      setHqReconnectAttempt(0);
    }
  };"""
toggle_new = """  const toggleHqMode = () => {
    const next = !hqEnabled;
    setHqEnabled(next);
    if (hqStorageKey) localStorage.setItem(hqStorageKey, String(next));
    
    // Notificar al backend/agente que active/desactive la transmision MJPEG HQ
    sendViewerCommand({ type: next ? 'start_hq' : 'stop_hq' });
  };"""
content = content.replace(toggle_old, toggle_new)

# 4. Remove display style from img
content = content.replace(
    "style={{ display: hqEnabled && hqState === 'open' ? 'none' : 'block' }}",
    "style={{ display: 'block' }}"
)

# 5. Remove video tag
content = re.sub(
    r'\{\/\*\s*── Video HQ \(H\.264 MSE\) — superpuesto, visible solo cuando HQ activo ──\s*\*\/.*?/>',
    '{/* Video HQ MSE removido en favor de MJPEG sobre WebSocket estandar */}',
    content,
    flags=re.DOTALL
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to App.tsx")
