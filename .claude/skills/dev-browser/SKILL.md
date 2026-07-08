---
name: dev-browser
description: Browser automation with persistent page state. Use when users ask to navigate websites, fill forms, take screenshots, extract web data, test web apps, debug browser issues, or automate browser workflows. Trigger phrases include "go to [url]", "click on", "fill out the form", "take a screenshot", "scrape", "automate", "test the website", "log into", "debug", "console errors", "network requests", or any browser interaction request.
---

# Dev Browser

A CLI for controlling browsers with sandboxed JavaScript scripts. Scripts run in a QuickJS WASM sandbox with no host filesystem or network access, making it safe to pre-approve.

## Installation

```bash
npm install -g dev-browser
dev-browser install    # installs Playwright + Chromium
```

## Permissions

Add to `.claude/settings.json` or `~/.claude/settings.json` so dev-browser runs without permission prompts:

```json
{
  "permissions": {
    "allow": ["Bash(dev-browser *)"]
  }
}
```

This is safe because scripts run in a sandboxed QuickJS WASM environment with no host access.

## Usage

Pipe JavaScript to `dev-browser` via stdin:

**macOS/Linux:**

```bash
dev-browser --headless <<'EOF'
const page = await browser.getPage("main");
await page.goto("https://example.com");
console.log(await page.title());
EOF
```

**Windows PowerShell:**

```powershell
@'
const page = await browser.getPage("main");
await page.goto("https://example.com");
console.log(await page.title());
'@ | dev-browser --headless
```

### CLI Flags

| Flag                    | Purpose                                                        |
| ----------------------- | -------------------------------------------------------------- |
| `--headless`            | Launch headless Chromium and run script via stdin              |
| `--connect`             | Connect to running Chrome instance (requires remote debugging) |
| `--timeout N`           | Script execution timeout in seconds (default: 30)              |
| `--ignore-https-errors` | Accept self-signed certificates                                |
| `--help`                | Full LLM usage guide with API reference                        |

### Connect to Running Chrome

Connect to the user's logged-in Chrome to reuse sessions/cookies:

```bash
# User must launch Chrome with remote debugging first:
# macOS: /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
# Windows: chrome.exe --remote-debugging-port=9222

dev-browser --connect <<'EOF'
const tabs = await browser.listPages();
console.log(JSON.stringify(tabs, null, 2));
EOF
```

## Script API

Scripts run in a sandboxed QuickJS runtime (not Node.js). Available globals:

### Browser Control

```javascript
browser.getPage(nameOrId); // Get/create named page, or connect to tab by targetId
browser.newPage(); // Create anonymous page (cleaned up after script)
browser.listPages(); // List all tabs: [{id, url, title, name}]
browser.closePage(name); // Close a named page
```

### File I/O (restricted to ~/.dev-browser/tmp/)

```javascript
await saveScreenshot(buf, name); // Save screenshot buffer, returns path
await writeFile(name, data); // Write file, returns path
await readFile(name); // Read file, returns content
```

### Output

```javascript
console.log / warn / error / info; // Routed to CLI stdout/stderr
```

### Pages Are Full Playwright Page Objects

`goto`, `click`, `fill`, `locator`, `evaluate`, `screenshot`, and everything else from the [Playwright Page API](https://playwright.dev/docs/api/class-page).

### AI Snapshots

```javascript
const snapshot = await page.snapshotForAI({
  track: true,
  depth: 5,
  timeout: 5000,
});
// Returns { full, incremental? } with semantic roles and stable element refs like:
// button "Submit" [ref=e5]
// link "Home" [ref=e1]
```

## Key Principles

1. **Small scripts**: Each script should do ONE thing (navigate, click, fill, check)
2. **Evaluate state**: Always log/return state at the end to decide next steps
3. **Use named pages**: `browser.getPage("checkout")` persists across scripts. Navigate once, reuse across invocations
4. **Snapshots for discovery**: When you don't know a page's layout, use `page.snapshotForAI()` to discover elements
5. **Source code as ground truth**: For local/dev sites, read the source code to write selectors directly instead of relying on snapshots

## Example Workflows

### Navigate and Extract

```javascript
const page = await browser.getPage("main");
await page.goto("https://example.com");
await page.waitForLoadState("networkidle");
const title = await page.title();
const text = await page.locator("main").textContent();
console.log(JSON.stringify({ title, text }));
```

### Fill a Form

```javascript
const page = await browser.getPage("main");
await page.fill("#email", "user@example.com");
await page.fill("#password", "secret");
await page.click('button[type="submit"]');
await page.waitForURL("**/dashboard");
console.log("Logged in:", page.url());
```

### Take a Screenshot

```javascript
const page = await browser.getPage("main");
const buf = await page.screenshot({ fullPage: true });
const path = await saveScreenshot(buf, "full-page.png");
console.log("Screenshot saved to:", path);
```

### Debug with Snapshot

```javascript
const page = await browser.getPage("main");
await page.goto("http://localhost:3000");
await page.waitForLoadState("networkidle");
const snapshot = await page.snapshotForAI();
console.log(snapshot.full);
```

### Monitor Console Errors

```javascript
const page = await browser.getPage("main");
page.on("console", (msg) => {
  if (msg.type() === "error") {
    console.error("PAGE ERROR:", msg.text());
  }
});
await page.goto("http://localhost:3000");
await page.waitForLoadState("networkidle");
// Wait a bit for async errors
await new Promise((r) => setTimeout(r, 3000));
```
