/**
 * 对本句追问中、待用户填写/补充/确认的全部槽位字段名加粗（不限固定词表）。
 * 仅排除指代语（如「以上信息」）和叙述性上下文。
 */
const ASK_PATTERN =
  /请(?:先|再)?(?:提供|补充|确认|填写|选择|告知|说明|输入|核对)|请问|(?:还|亦)?(?:需要|需)|需要您|请您|麻烦|烦请|请告诉我|请告知/

const ASK_LEAD =
  /(?:请(?:先|再)?(?:提供|补充|确认|填写|选择|告知|说明|输入|核对)|请问|(?:还|亦)?(?:需要|需)(?:您|你)?(?:再)?(?:提供|补充|确认|填写|告知)?|需要您(?:提供|补充|确认|填写|告知)|请您(?:提供|补充|确认|填写|告知)|麻烦(?:您|你)?(?:提供|补充|告知)|烦请(?:您|你)?(?:提供|补充|告知)|请告诉我(?:您|你)?(?:的)?|请告知(?:您|你)?(?:的)?)(?:您|你)?(?:的)?/

const ASK_FIELD_LIST = new RegExp(
  `(${ASK_LEAD.source})([\\u4e00-\\u9fffA-Za-z0-9·]{2,12}(?:[和、及与][\\u4e00-\\u9fffA-Za-z0-9·]{2,12})*)(?=[，。！？；：\\n]|$)`,
  'g',
)

const ASK_FIELD_SINGLE = new RegExp(
  `(${ASK_LEAD.source})([\\u4e00-\\u9fffA-Za-z0-9·]{2,12}?(?=[是为在及，。！？；：\\n]|$))`,
  'g',
)

const LIST_SEP = /[和、及与]/
const FIELD_TOKEN = /^[\u4e00-\u9fffA-Za-z0-9·]{2,12}$/

const SKIP_PREFIXES = ['以上', '上述', '以下', '如下', '这些', '这个', '那个']
const SKIP_TOKENS = new Set([
  '以上信息',
  '上述信息',
  '以下信息',
  '这些信息',
  '上述内容',
  '以下内容',
  '如下信息',
  '什么',
  '哪些',
  '多少',
  '如何',
  '是否',
  '能否',
  '一下',
  '具体',
  '详细',
  '正确',
  '准确',
  '完整',
])

function isSlotField(token: string): boolean {
  const t = token.trim()
  if (!t || !FIELD_TOKEN.test(t)) return false
  if (SKIP_TOKENS.has(t)) return false
  if (SKIP_PREFIXES.some((p) => t.startsWith(p))) return false
  if (/^\d+$/.test(t)) return false
  if (t.includes('还是')) return false
  return true
}

function boldToken(token: string): string {
  if (!isSlotField(token)) return token
  if (token.startsWith('**') && token.endsWith('**')) return token
  return `**${token}**`
}

function boldFieldList(body: string): string {
  return body
    .split(/([和、及与])/)
    .map((piece) => (LIST_SEP.test(piece) ? piece : boldToken(piece)))
    .join('')
}

function applyPatterns(text: string): string {
  let result = text
  for (const [pattern, formatter] of [
    [ASK_FIELD_LIST, (m: RegExpExecArray) => m[1] + boldFieldList(m[2])],
    [ASK_FIELD_SINGLE, (m: RegExpExecArray) => m[1] + boldToken(m[2])],
  ] as const) {
    const chunks: string[] = []
    let last = 0
    let match: RegExpExecArray | null
    const re = new RegExp(pattern.source, pattern.flags)
    while ((match = re.exec(result)) !== null) {
      chunks.push(result.slice(last, match.index))
      chunks.push(formatter(match))
      last = match.index + match[0].length
    }
    chunks.push(result.slice(last))
    result = chunks.join('')
  }
  return result
}

export function emphasizeSlotLabels(text: string): string {
  if (!text || !ASK_PATTERN.test(text)) return text
  return applyPatterns(text)
}

/** 将消息中的 **加粗** 转为安全 HTML（仅支持 strong，其余转义） */
export function formatMessageHtml(text: string): string {
  const emphasized = emphasizeSlotLabels(text)
  const escaped = emphasized
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  return escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}
