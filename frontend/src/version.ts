/** Versión del portal — debe coincidir con agente y backend en cada release. */
export const APP_VERSION = '3.2.6';
export const APP_BUILD = '2026-08-31';
export const APP_VERSION_TAG = 'keyboard-input-session-fix';
export const APP_VERSION_LABEL = `v${APP_VERSION}`;

/** Clave en localStorage para detectar deploy nuevo y purgar Service Worker. */
export const APP_VERSION_STORAGE_KEY = `apollo_portal_${APP_VERSION}_${APP_BUILD}`;
