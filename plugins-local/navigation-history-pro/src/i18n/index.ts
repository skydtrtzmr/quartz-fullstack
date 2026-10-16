const en = { navigation: "Page history", back: "Back", forward: "Forward" }
const zh = { navigation: "页面访问历史", back: "后退", forward: "前进" }
export function historyLabels(locale: string) {
  return locale.toLowerCase().startsWith("zh") ? zh : en
}
