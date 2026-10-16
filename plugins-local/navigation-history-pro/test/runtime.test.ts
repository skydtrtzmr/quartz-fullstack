import { afterEach, expect, it, vi } from "vitest"
import { readMarker, STATE_KEY } from "../src/history"

afterEach(() => { vi.unstubAllGlobals(); vi.resetModules() })

it("tracks real SPA entries, restores scroll on native traversal, rebinds after navigation and branches correctly", async () => {
  const document = new EventTarget()
  const window = new EventTarget()
  const store = new Map<string, string>()
  const root = { dataset: { historyRoot: "/demo", historyScroll: "true" } }
  class Button extends EventTarget {
    disabled = true
    constructor(readonly dataset: { historyDirection: string }) { super() }
    click() { this.dispatchEvent(new Event("click")) }
  }
  const back = new Button({ historyDirection: "back" })
  const forward = new Button({ historyDirection: "forward" })
  Object.assign(document, { querySelector: () => root, querySelectorAll: () => [back, forward] })
  const location = { href: "https://test.local/demo/", origin: "https://test.local" }
  const stack: { url: string; state: unknown }[] = [{ url: location.href, state: { otherPlugin: 1 } }]
  let cursor = 0
  let cleanups: (() => void)[] = []
  const history = {
    get state() { return stack[cursor]!.state },
    pushState(data: unknown, _unused: string, url?: string | URL | null) {
      location.href = new URL(String(url ?? location.href), location.href).href
      stack.splice(cursor + 1)
      stack.push({ url: location.href, state: data })
      cursor++
    },
    replaceState(data: unknown, _unused: string, url?: string | URL | null) {
      location.href = new URL(String(url ?? location.href), location.href).href
      stack[cursor] = { url: location.href, state: data }
    },
    go(delta: number) {
      cursor += delta
      location.href = stack[cursor]!.url
      window.dispatchEvent(new Event("popstate"))
      document.dispatchEvent(new Event("prenav"))
      cleanups.forEach(fn => fn()); cleanups = []
      document.dispatchEvent(new Event("nav"))
    },
  }
  const scrollTo = vi.fn()
  Object.assign(window, { addCleanup: (fn: () => void) => cleanups.push(fn), scrollTo })
  vi.stubGlobal("window", window)
  let nextId = 0
  // LAN HTTP has getRandomValues but no randomUUID.
  vi.stubGlobal("crypto", { getRandomValues: (value: Uint32Array) => { value.fill(++nextId); return value } })
  vi.stubGlobal("document", document)
  vi.stubGlobal("history", history)
  vi.stubGlobal("location", location)
  vi.stubGlobal("scrollX", 0)
  vi.stubGlobal("scrollY", 0)
  vi.stubGlobal("sessionStorage", { getItem: (key: string) => store.get(key) ?? null, setItem: (key: string, value: string) => store.set(key, value) })
  vi.stubGlobal("requestAnimationFrame", (fn: FrameRequestCallback) => { fn(0); return 1 })
  await import("../src/components/scripts/history.inline")
  document.dispatchEvent(new Event("nav"))
  expect([back.disabled, forward.disabled]).toEqual([true, true])
  expect(history.state).toMatchObject({ otherPlugin: 1 })
  const initialId = readMarker(history.state)!.id

  vi.stubGlobal("scrollY", 420)
  document.dispatchEvent(new Event("prenav"))
  cleanups.forEach(fn => fn()); cleanups = []
  vi.stubGlobal("scrollY", 0) // Quartz resets page scroll before pushing the next URL.
  history.pushState({ anotherPlugin: true }, "", "/demo/_dimensions/status/open?scope=folder#value")
  document.dispatchEvent(new Event("nav"))
  expect([back.disabled, forward.disabled]).toEqual([false, true])
  expect(history.state).toMatchObject({ anotherPlugin: true })
  back.click()
  expect(location.href).toBe("https://test.local/demo/")
  expect(readMarker(history.state)!.id).toBe(initialId)
  expect([back.disabled, forward.disabled]).toEqual([true, false])
  expect(scrollTo).toHaveBeenLastCalledWith({ left: 0, top: 420, behavior: "instant" })
  forward.click()
  expect(location.href).toBe("https://test.local/demo/_dimensions/status/open?scope=folder#value")
  history.go(-1) // Browser back uses the same state and listeners.
  history.pushState({}, "", "/demo/new")
  document.dispatchEvent(new Event("nav"))
  expect(stack).toHaveLength(2)
  expect([back.disabled, forward.disabled]).toEqual([false, true])
  expect(store.has(`${STATE_KEY}:https://test.local:/demo`)).toBe(true)
})
