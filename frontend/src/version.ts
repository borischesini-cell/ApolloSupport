/** Versión del portal — debe coincidir con agente y backend en cada release. */
export const APP_VERSION = '3.3.40';
export const APP_BUILD = '2026-10-07';
export const APP_VERSION_TAG = 'fps-p2p';
export const APP_VERSION_LABEL = `v${APP_VERSION}`;

/** Clave en localStorage para detectar deploy nuevo y purgar Service Worker. */
export const APP_VERSION_STORAGE_KEY = `apollo_portal_${APP_VERSION}_${APP_BUILD}`;
