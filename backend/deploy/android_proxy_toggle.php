<?php
/**
 * Apollo — Activar / desactivar dispositivo en misi_licand
 * Subir junto a android_proxy.php en www.masterisi.com.ar (NO reemplaza el existente).
 *
 * Uso:
 *   GET ?key=...&id=123&status=1
 */
define('APOLLO_SECRET_KEY', 'Apollo_Masterisi_Proxy_2025_SecureKey');

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
    echo json_encode(['error' => 'Unauthorized', 'message' => 'Clave inválida']);
    exit;
}

$DB_HOST = 'localhost';
$DB_USER = 'masterisi_root';
$DB_PASS = 'Isi-2010';
$DB_NAME = 'masterisi_licenmovil';

$mysqli = new mysqli($DB_HOST, $DB_USER, $DB_PASS, $DB_NAME);
$mysqli->set_charset('utf8mb4');
if ($mysqli->connect_error) {
    http_response_code(500);
    echo json_encode(['error' => 'db_connect', 'message' => $mysqli->connect_error]);
    exit;
}

$id = intval($_GET['id'] ?? $_POST['id'] ?? 0);
$status = intval($_GET['status'] ?? $_POST['status'] ?? 0);
if ($id <= 0) {
    http_response_code(400);
    echo json_encode(['error' => 'invalid_id', 'message' => 'ID de dispositivo inválido']);
    exit;
}
if ($status !== 0 && $status !== 1) {
    http_response_code(400);
    echo json_encode(['error' => 'invalid_status', 'message' => 'Estado inválido (0 o 1)']);
    exit;
}

$stmt = $mysqli->prepare('UPDATE misi_licand SET lc_habilitado = ? WHERE KeyId = ?');
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
$mysqli->close();
