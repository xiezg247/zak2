import { reactive } from 'vue'

export type ConfirmOptions = {
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

export type PromptOptions = {
  title?: string
  message?: string
  initialValue?: string
  placeholder?: string
  confirmText?: string
  cancelText?: string
}

export type DialogRequest = {
  kind: 'confirm' | 'prompt'
  title: string
  message?: string
  initialValue?: string
  placeholder?: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  resolve: (value: boolean | string | null) => void
}

const state = reactive<{ current: DialogRequest | null }>({ current: null })

function settle(value: boolean | string | null) {
  const req = state.current
  state.current = null
  if (req) req.resolve(value)
}

export function confirmDialog(options: ConfirmOptions = {}): Promise<boolean> {
  return new Promise<boolean>((resolve) => {
    state.current = {
      kind: 'confirm',
      title: options.title ?? '确认操作',
      message: options.message,
      confirmText: options.confirmText,
      cancelText: options.cancelText,
      danger: options.danger,
      resolve: (v) => resolve(v === true),
    }
  })
}

export function promptDialog(options: PromptOptions = {}): Promise<string | null> {
  return new Promise<string | null>((resolve) => {
    state.current = {
      kind: 'prompt',
      title: options.title ?? '请输入',
      message: options.message,
      initialValue: options.initialValue,
      placeholder: options.placeholder,
      confirmText: options.confirmText,
      cancelText: options.cancelText,
      resolve: (v) => resolve(v == null ? null : String(v)),
    }
  })
}

export function useDialog() {
  return { state, settle }
}
