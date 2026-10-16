import { describe, expect, it } from "vitest"
import { STATE_KEY, available, inDomain, moveTo, pushEntry, readMarker, restoreLedger, withMarker, type Ledger } from "../src/history"

const origin = "https://site.local"
const url = (path: string) => `${origin}/domain${path}`
const first: Ledger = { version: 1, root: "/domain", cursor: 0,
  entries: [{ id: "a", url: url("/"), x: 0, y: 125 }] }
const add = (state: Ledger, id: string, path: string) => pushEntry(state, { id, url: url(path), x: 0, y: 0 })

describe("domain history", () => {
  it("does not enable back for an external landing, including a populated browser history", () => {
    expect(available(first)).toEqual({ back: false, forward: false })
    expect(moveTo(first, undefined, url("/"))).toBeUndefined()
    expect(moveTo(first, { root: "/other", id: "a" }, url("/"))).toBeUndefined()
  })
  it("preserves query and anchor entries and follows native back/forward markers", () => {
    const second = add(first, "b", "/_dimensions/status/open?scope=folder&filter=type:A#section")
    expect(second.entries[1]?.url).toContain("?scope=folder&filter=type:A#section")
    const back = moveTo(second, { root: first.root, id: "a" }, url("/"))!
    expect(available(back)).toEqual({ back: false, forward: true })
    expect(back.entries[0]?.y).toBe(125)
    const forward = moveTo(back, { root: first.root, id: "b" }, second.entries[1]!.url)!
    expect(available(forward)).toEqual({ back: true, forward: false })
  })
  it("discards the native forward branch when a new link is opened after going back", () => {
    const state = add(add(first, "b", "/b"), "c", "/c")
    const back = moveTo(state, { root: first.root, id: "b" }, url("/b"))!
    const branched = add(back, "d", "/d")
    expect(branched.entries.map(e => e.id)).toEqual(["a", "b", "d"])
    expect(available(branched).forward).toBe(false)
  })
  it("treats path boundaries and origin as part of domain identity", () => {
    expect(inDomain(new URL(url("")), origin, "/domain")).toBe(true)
    expect(inDomain(new URL(url("/folder")), origin, "/domain")).toBe(true)
    expect(inDomain(new URL(`${origin}/domain-extra/`), origin, "/domain")).toBe(false)
    expect(inDomain(new URL("https://other.local/domain/"), origin, "/domain")).toBe(false)
    expect(inDomain(new URL(`${origin}/any`), origin, "/")).toBe(true)
  })
  it("restores after reload but rejects stale, foreign or corrupt stored records", () => {
    expect(restoreLedger(JSON.stringify(first), "/domain", origin)).toEqual(first)
    expect(restoreLedger(JSON.stringify(first), "/other", origin)).toBeUndefined()
    expect(restoreLedger(JSON.stringify({ ...first, cursor: 7 }), "/domain", origin)).toBeUndefined()
    expect(restoreLedger(JSON.stringify({ ...first, entries: [...first.entries, ...first.entries] }), "/domain", origin)).toBeUndefined()
    expect(restoreLedger(JSON.stringify(first), "/domain", "https://other.local")).toBeUndefined()
    expect(restoreLedger("bad json", "/domain", origin)).toBeUndefined()
  })
  it("preserves other plugins' history state and rejects unknown traversal targets", () => {
    const marker = { root: first.root, id: "a" }
    const state = withMarker({ existingPlugin: { n: 2 } }, marker)
    expect(state.existingPlugin).toEqual({ n: 2 })
    expect(readMarker(state)).toEqual(marker)
    expect(readMarker({ [STATE_KEY]: { id: 12 } })).toBeUndefined()
    expect(moveTo(first, marker, url("/different"))).toBeUndefined()
  })
})
