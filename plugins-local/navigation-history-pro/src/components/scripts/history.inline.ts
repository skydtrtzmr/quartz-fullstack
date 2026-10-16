import { STATE_KEY, available, inDomain, moveTo, pushEntry, readMarker, restoreLedger, withMarker,
  type Entry, type Ledger } from "../../history"

function installNavigationHistory() {
  const host = window as Window & { __navigationHistoryPro?: boolean }
  if (host.__navigationHistoryPro) return
  host.__navigationHistoryPro = true
  const nativePush = history.pushState.bind(history)
  const nativeReplace = history.replaceState.bind(history)
  let ledger: Ledger | undefined
  let root = ""
  let traveling = false
  let restorePending = false
  let replacingPage = false
  let revision = 0
  let scrollTimer: ReturnType<typeof setTimeout> | undefined
  const buttonSelector = ".navigation-history-pro [data-history-direction]"
  const storageKey = () => `${STATE_KEY}:${location.origin}:${root}`
  const controls = () => document.querySelector<HTMLElement>(".navigation-history-pro")
  // randomUUID requires HTTPS; getRandomValues also works on LAN HTTP deployments.
  const entry = (): Entry => ({
    id: crypto.randomUUID?.() ?? Array.from(crypto.getRandomValues(new Uint32Array(4)), n => n.toString(16)).join("-"),
    url: location.href, x: scrollX, y: scrollY,
  })
  function persist() {
    try { if (ledger) sessionStorage.setItem(storageKey(), JSON.stringify(ledger)) } catch { /* memory works without storage */ }
  }
  function updateButtons() {
    const state = available(ledger)
    document.querySelectorAll<HTMLButtonElement>(buttonSelector).forEach(button => {
      const enabled = button.dataset.historyDirection === "back" ? state.back : state.forward
      button.disabled = traveling || !enabled || !controls() || !inDomain(new URL(location.href), location.origin, root)
    })
  }
  function saveScroll() {
    const current = ledger?.entries[ledger.cursor]
    if (!current || restorePending) return
    current.x = scrollX
    current.y = scrollY
    persist()
  }
  function establish() {
    const control = controls()
    if (!control) { ledger = undefined; root = ""; return }
    const nextRoot = control.dataset.historyRoot ?? "/"
    if (root !== nextRoot || !ledger) {
      root = nextRoot
      let raw: string | null = null
      try { raw = sessionStorage.getItem(storageKey()) } catch { /* private mode */ }
      ledger = restoreLedger(raw, root, location.origin)
    }
    if (!inDomain(new URL(location.href), location.origin, root)) { ledger = undefined; return }
    const marker = readMarker(history.state)
    const previous = ledger && moveTo(ledger, marker, location.href)
    if (previous) ledger = previous
    else {
      const first = entry()
      ledger = { version: 1, root, entries: [first], cursor: 0 }
      nativeReplace(withMarker(history.state, { root, id: first.id }), "")
    }
    persist()
  }

  history.pushState = (data, unused, url) => {
    if (!replacingPage) saveScroll()
    const destination = new URL(url == null ? location.href : String(url), location.href)
    if (ledger && root && controls() && inDomain(destination, location.origin, root)) {
      const next = { ...entry(), url: destination.href, x: 0, y: 0 }
      nativePush(withMarker(data, { root, id: next.id }), unused, url)
      ledger = pushEntry(ledger, next)
      restorePending = false
      persist()
    } else {
      nativePush(data, unused, url)
      ledger = undefined
    }
    traveling = false
    revision++
    updateButtons()
  }
  history.replaceState = (data, unused, url) => {
    const destination = new URL(url == null ? location.href : String(url), location.href)
    const current = ledger?.entries[ledger.cursor]
    if (current && inDomain(destination, location.origin, root)) {
      nativeReplace(withMarker(data, { root, id: current.id }), unused, url)
      current.url = destination.href
      persist()
    } else nativeReplace(data, unused, url)
    updateButtons()
  }

  // These listeners live for the document lifetime; only the page's button listeners use addCleanup.
  window.addEventListener("popstate", () => {
    saveScroll()
    restorePending = true
    traveling = true
    revision++
    establish()
    updateButtons()
  })
  window.addEventListener("scroll", () => {
    clearTimeout(scrollTimer)
    scrollTimer = setTimeout(saveScroll, 120)
  }, { passive: true })
  window.addEventListener("pagehide", saveScroll)
  document.addEventListener("prenav", () => { saveScroll(); replacingPage = true })
  document.addEventListener("nav", setup)
  document.addEventListener("render", () => { establish(); bindButtons() })

  const bound = new WeakSet<HTMLButtonElement>()
  function bindButtons() {
    document.querySelectorAll<HTMLButtonElement>(buttonSelector).forEach(button => {
      if (bound.has(button)) return
      bound.add(button)
      const click = () => {
        if (button.disabled || traveling) return
        saveScroll()
        traveling = true
        updateButtons()
        history.go(button.dataset.historyDirection === "back" ? -1 : 1)
      }
      button.addEventListener("click", click)
      window.addCleanup(() => { button.removeEventListener("click", click); bound.delete(button) })
    })
    updateButtons()
  }
  function setup() {
    replacingPage = false
    establish()
    traveling = false
    bindButtons()
    if (restorePending && controls()?.dataset.historyScroll !== "false") {
      const current = ledger?.entries[ledger.cursor]
      const expected = revision
      // Wait for SPA listeners to replace/initialize their DOM before restoring page scroll.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (expected !== revision) return
        if (current) window.scrollTo({ left: current.x, top: current.y, behavior: "instant" })
        restorePending = false
      }))
    } else restorePending = false
  }
  establish()
}

installNavigationHistory()
