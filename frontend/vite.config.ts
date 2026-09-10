import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

const APP_VERSION = '3.2.6'
const APP_BUILD = '2026-08-31'

function injectSwVersion(swBody: string): string {
  return swBody
    .replace(/__APOLLO_VERSION__/g, APP_VERSION)
    .replace(/__APOLLO_BUILD__/g, APP_BUILD)
}

function apolloVersionPlugin(): Plugin {
  return {
    name: 'apollo-version-artifacts',
    closeBundle() {
      const root = path.resolve(__dirname)
      const dist = path.join(root, 'dist')
      const swSrc = path.join(root, 'public', 'sw.js')
      if (!fs.existsSync(dist) || !fs.existsSync(swSrc)) return

      const swRaw = fs.readFileSync(swSrc, 'utf8')
      const swBody = injectSwVersion(swRaw)
      const swName = `sw-v${APP_VERSION}.js`
      const swVersioned = `// Apollo Portal SW v${APP_VERSION} build ${APP_BUILD}\n${swBody}`
      fs.writeFileSync(path.join(dist, swName), swVersioned)

      // Stub legacy: purga caches y no intercepta la app
      fs.writeFileSync(
        path.join(dist, 'sw.js'),
        `// Legacy SW — usar /${swName}\n` +
        `self.addEventListener('install', (e) => { e.waitUntil(self.skipWaiting()); });\n` +
        `self.addEventListener('activate', (e) => {\n` +
        `  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k)))).then(() => self.clients.claim()));\n` +
        `});\n` +
        `self.addEventListener('fetch', (e) => { e.respondWith(fetch(e.request)); });\n`,
      )

      fs.writeFileSync(
        path.join(dist, 'version.txt'),
        `version=${APP_VERSION}\nbuild=${APP_BUILD}\nsw=/${swName}\n`,
      )

      const manifestPath = path.join(dist, 'manifest.json')
      if (fs.existsSync(manifestPath)) {
        const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
        manifest.version = APP_VERSION
        fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
      }

      const indexPath = path.join(dist, 'index.html')
      if (fs.existsSync(indexPath)) {
        let html = fs.readFileSync(indexPath, 'utf8')
        html = html.replace(
          /content="[\d.]+"(?=[^>]*apollo-version)/,
          `content="${APP_VERSION}"`,
        )
        html = html.replace(
          /content="[\d-]+"(?=[^>]*apollo-build)/,
          `content="${APP_BUILD}"`,
        )
        if (!html.includes('apollo-build')) {
          html = html.replace(
            '<head>',
            `<head>\n    <meta name="apollo-build" content="${APP_BUILD}" />`,
          )
        }
        fs.writeFileSync(indexPath, html)
      }

      console.log(`[apollo] dist/${swName} + version.txt (v${APP_VERSION})`)
    },
  }
}

export default defineConfig({
  plugins: [react(), apolloVersionPlugin()],
})
