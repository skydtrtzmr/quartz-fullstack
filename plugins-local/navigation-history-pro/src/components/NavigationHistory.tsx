import type { QuartzComponent, QuartzComponentConstructor } from "@quartz-community/types"
import { defaultOptions, type Options } from "../options"
import { historyLabels } from "../i18n"
// @ts-expect-error inline script is bundled as text by tsup
import script from "./scripts/history.inline.ts"
import styles from "./styles/history.scss"

export default ((value?: Partial<Options>) => {
  const options = { ...defaultOptions, ...value }
  const NavigationHistory: QuartzComponent = ({ cfg, displayClass }) => {
  // baseUrl is host/domain without a protocol; only the pathname defines the boundary.
  const base = new URL(`https://${(cfg.baseUrl ?? "localhost").replace(/^https?:\/\//, "")}`).pathname.replace(/\/$/, "") || "/"
  const labels = historyLabels(cfg.locale ?? "en-US")
  return <nav class={["navigation-history-pro", displayClass].filter(Boolean).join(" ")}
    aria-label={labels.navigation} data-history-root={base}
    data-history-scroll={String(options.restoreScroll)}>
    {(["back", "forward"] as const).map(direction => <button type="button" disabled
      data-history-direction={direction} aria-label={labels[direction]} title={labels[direction]}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
        stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d={direction === "back" ? "M19 12H5m7-7-7 7 7 7" : "M5 12h14m-7-7 7 7-7 7"} />
      </svg>
      {options.showLabels && <span>{labels[direction]}</span>}
    </button>)}
  </nav>
}

NavigationHistory.css = styles
NavigationHistory.afterDOMLoaded = script
  return NavigationHistory
}) satisfies QuartzComponentConstructor
