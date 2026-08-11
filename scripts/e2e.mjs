// Browser smoke test of the core workflow (project → upload → detect →
// review → export). Requires the app running (`make dev`) and playwright-core:
//
//   npm install --no-save playwright-core
//   CHROMIUM=/path/to/chrome node scripts/e2e.mjs
//
// CHROMIUM defaults to the standard macOS Google Chrome location.
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { chromium } from 'playwright-core'

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const executablePath =
  process.env.CHROMIUM ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const browser = await chromium.launch({ executablePath })
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } })
const errors = []
page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`))
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(`console: ${msg.text()}`)
})

const fail = (message) => {
  console.error(`FAIL: ${message}`)
  process.exitCode = 1
}

await page.goto('http://localhost:5173/')

// Create a project and upload the sample scan.
await page.fill('input[placeholder="New project name"]', `e2e-${Date.now()}`)
await page.click('button:has-text("Create project")')
await page.waitForURL(/\/projects\//)
const [chooser] = await Promise.all([
  page.waitForEvent('filechooser'),
  page.click('button:has-text("Add images…")'),
])
await chooser.setFiles(path.join(repo, 'assets/raw-images/eyes-11.png'))
await page.waitForSelector('.card img.thumb', { timeout: 20000 })

// Detect.
await page.click('.card')
await page.waitForSelector('.canvas-wrap img')
await page.click('button:has-text("Detect elements")')
await page.waitForSelector('svg polygon', { timeout: 60000 })
const regionCount = await page.locator('svg polygon').count()
console.log('regions rendered:', regionCount)
if (regionCount < 25) fail(`expected >= 25 regions, got ${regionCount}`)

// Review: jump to a flagged region and approve it.
const nextFlagged = page.locator('button', { hasText: 'Next ⚑' })
if (await nextFlagged.isEnabled()) {
  await nextFlagged.click()
  await page.click('button:has-text("Approve")')
  await page.waitForTimeout(400)
  console.log('approved a flagged region')
}

// Export the page; review strip appears.
await page.click('button:has-text("Export page")')
await page.waitForSelector('.export-strip img', { timeout: 60000 })
console.log('exports shown:', await page.locator('.export-strip img').count())

// Clean full-page export.
await page.click('button:has-text("Clean full page")')
await page.waitForSelector('a:has-text("open ↗")', { timeout: 60000 })
console.log('clean page exported')

// Contact sheet link present after export.
if ((await page.locator('a:has-text("Contact sheet")').count()) !== 1) fail('contact sheet link missing')

// Manual polygon: 4 clicks + Enter creates a region.
await page.click('button:has-text("Polygon")')
const box = await page.locator('.canvas-wrap').boundingBox()
for (const [fx, fy] of [[0.3, 0.3], [0.45, 0.3], [0.45, 0.45], [0.3, 0.45]]) {
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy)
  await page.waitForTimeout(100)
}
await page.keyboard.press('Enter')
await page.waitForTimeout(800)
const afterManual = await page.locator('svg polygon').count()
console.log('regions after manual polygon:', afterManual)
if (afterManual !== regionCount + 1) fail('manual polygon did not create a region')

const realErrors = errors.filter((entry) => !entry.includes('favicon'))
if (realErrors.length) fail(`browser errors: ${realErrors.join(' | ')}`)
console.log(process.exitCode ? 'E2E FAILED' : 'E2E OK')
await browser.close()
