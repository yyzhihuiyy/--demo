export const money = (cents: number) => new Intl.NumberFormat('zh-CN', {
  style: 'currency', currency: 'CNY',
}).format(cents / 100)

export const percent = (value: number | null | undefined) => value == null ? '暂无样本' : `${(value * 100).toFixed(1)}%`
export const dateTime = (value: string | null | undefined) => value ? new Date(value).toLocaleString('zh-CN') : '—'
