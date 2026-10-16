export const STATE_KEY = "quartz:navigation-history-pro"
export interface Entry { id: string; url: string; x: number; y: number }
export interface Ledger { version: 1; root: string; entries: Entry[]; cursor: number }
export interface Marker { root: string; id: string }

export function inDomain(url: URL, origin: string, root: string): boolean {
  return url.origin === origin && (root === "/" || url.pathname === root || url.pathname.startsWith(`${root}/`))
}

export function readMarker(state: unknown): Marker | undefined {
  if (!state || typeof state !== "object") return
  const marker = (state as Record<string, unknown>)[STATE_KEY] as Partial<Marker> | undefined
  if (marker && typeof marker.root === "string" && typeof marker.id === "string") return marker as Marker
}

export function withMarker(state: unknown, marker: Marker): Record<string, unknown> {
  return { ...(state && typeof state === "object" ? state : {}), [STATE_KEY]: marker }
}

export function restoreLedger(raw: string | null, root: string, origin: string): Ledger | undefined {
  try {
    const value = JSON.parse(raw ?? "null") as Ledger | null
    if (!value || value.version !== 1 || value.root !== root || !Array.isArray(value.entries) ||
      !Number.isInteger(value.cursor) || value.cursor < 0 || value.cursor >= value.entries.length) return
    const ids = new Set<string>()
    for (const entry of value.entries) {
      if (!entry || typeof entry.id !== "string" || ids.has(entry.id) || typeof entry.url !== "string" ||
        !inDomain(new URL(entry.url), origin, root) || !Number.isFinite(entry.x) || !Number.isFinite(entry.y)) return
      ids.add(entry.id)
    }
    return value
  } catch { return }
}

/** Each entry corresponds to an actual native history entry, including hash/query changes. */
export function pushEntry(ledger: Ledger, entry: Entry): Ledger {
  return { ...ledger, entries: [...ledger.entries.slice(0, ledger.cursor + 1), entry], cursor: ledger.cursor + 1 }
}

export function moveTo(ledger: Ledger, marker: Marker | undefined, url: string): Ledger | undefined {
  if (!marker || marker.root !== ledger.root) return
  const cursor = ledger.entries.findIndex(entry => entry.id === marker.id && entry.url === url)
  return cursor < 0 ? undefined : { ...ledger, cursor }
}

export function available(ledger: Ledger | undefined) {
  return { back: !!ledger && ledger.cursor > 0, forward: !!ledger && ledger.cursor < ledger.entries.length - 1 }
}
