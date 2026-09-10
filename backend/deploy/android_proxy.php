<?php
/**
 * Apollo Android Devices Proxy
 * Consulta la tabla misi_licand y devuelve JSON
 * 
 * Seguridad: requiere el header X-Apollo-Key con el token correcto
 * 
 * Uso:
 *   GET  /android_proxy.php?action=summary
 *   GET  /android_proxy.php?action=client&code=0115
 *   POST /android_proxy.php?action=toggle&id=123&status=1
 */

// Token de seguridad (debe coincidir con el configurado en erp_licensing.py)
define('APOLLO_SECRET_KEY', 'Apollo_Masterisi_Proxy_2025_SecureKey');

// Configuración de la base de datos
$DB_HOST = 'localhost';
$DB_USER = 'masterisi_root';
$DB_PASS = 'Isi-2010';
$DB_NAME = 'masterisi_licenmovil';

// Headers CORS y JSON
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: X-Apollo-Key, Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

$auth_header = $_SERVER['HTTP_X_APOLLO_KEY'] ?? '';
$auth_query = $_GET['key'] ?? $_POST['key'] ?? '';
if ($auth_header !== APOLLO_SECRET_KEY && $auth_query !== APOLLO_SECRET_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized', 'message' => 'Invalid or missing X-Apollo-Key header']);
    exit;
}

// Conectar a la base de datos
$mysqli = new mysqli($DB_HOST, $DB_USER, $DB_PASS, $DB_NAME);
$mysqli->set_charset('utf8mb4');

if ($mysqli->connect_error) {
    http_response_code(500);
    echo json_encode(['error' => 'DB Connection failed: ' . $mysqli->connect_error]);
    exit;
}

$action = $_GET['action'] ?? $_POST['action'] ?? 'summary';

if ($action === 'summary') {
    // Resumen agrupado por cliente y app
    $sql = "
        SELECT
            LEFT(lc_serial_gescom, 4) AS client_code,
            lc_app,
            COUNT(*) AS total,
            SUM(CASE WHEN lc_habilitado = 1 THEN 1 ELSE 0 END) AS habilitados,
            SUM(CASE WHEN lc_habilitado = 0 THEN 1 ELSE 0 END) AS deshabilitados,
            MAX(lc_ult_acceso) AS ultimo_acceso,
            MIN(lc_fecha_registro) AS primer_registro
        FROM misi_licand
        WHERE lc_serial_gescom IS NOT NULL AND lc_serial_gescom != ''
        GROUP BY LEFT(lc_serial_gescom, 4), lc_app
        ORDER BY LEFT(lc_serial_gescom, 4), lc_app
    ";
    
    $result = $mysqli->query($sql);
    if (!$result) {
        http_response_code(500);
        echo json_encode(['error' => 'Query failed: ' . $mysqli->error]);
        exit;
    }
    
    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
    
    echo json_encode($rows, JSON_UNESCAPED_UNICODE);
    
} elseif ($action === 'client') {
    // Detalle de dispositivos de un cliente específico
    $code = $_GET['code'] ?? '';
    if (!$code || strlen($code) != 4 || !ctype_alnum($code)) {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid client code. Must be 4 alphanumeric characters.']);
        exit;
    }
    
    $stmt = $mysqli->prepare("
        SELECT
            KeyId,
            lc_android_id,
            lc_imei_serial,
            lc_serial_gescom,
            lc_cuenta_google,
            lc_android_so,
            lc_no_telefono,
            lc_habilitado,
            lc_ult_acceso,
            lc_fecha_registro,
            lc_fabricante,
            lc_app
        FROM misi_licand
        WHERE LEFT(lc_serial_gescom, 4) = ?
        ORDER BY lc_app, lc_habilitado DESC, lc_ult_acceso DESC
    ");
    
    $stmt->bind_param('s', $code);
    $stmt->execute();
    $result = $stmt->get_result();
    
    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
    
    echo json_encode($rows, JSON_UNESCAPED_UNICODE);
    
} elseif ($action === 'toggle') {
    // Activar o desactivar un dispositivo (GET o POST)
    $id = intval($_GET['id'] ?? $_POST['id'] ?? 0);
    $status = intval($_GET['status'] ?? $_POST['status'] ?? 0);
    if ($id <= 0) {
        http_response_code(400);
        echo json_encode(['error' => 'invalid_id', 'message' => 'ID de dispositivo inválido']);
        exit;
    }
    if ($status !== 0 && $status !== 1) {
        http_response_code(400);
        echo json_encode(['error' => 'invalid_status', 'message' => 'Estado inválido (use 0 o 1)']);
        exit;
    }
    $stmt = $mysqli->prepare("UPDATE misi_licand SET lc_habilitado = ? WHERE KeyId = ?");
    if (!$stmt) {
        http_response_code(500);
        echo json_encode(['error' => 'prepare_failed', 'message' => $mysqli->error]);
        exit;
    }
    $stmt->bind_param('ii', $status, $id);
    if (!$stmt->execute()) {
        http_response_code(500);
        echo json_encode(['error' => 'update_failed', 'message' => $stmt->error]);
        exit;
    }
    if ($stmt->affected_rows === 0) {
        http_response_code(404);
        echo json_encode(['error' => 'not_found', 'message' => "No se encontró dispositivo KeyId=$id"]);
        exit;
    }
    echo json_encode(['status' => 'success', 'KeyId' => $id, 'lc_habilitado' => $status]);

} else {
    http_response_code(400);
    echo json_encode(['error' => 'invalid_action', 'message' => 'Acción inválida. Use: summary, client, toggle']);
}

$mysqli->close();
?>
