import { onBeforeUnmount, ref } from 'vue'

export type SpeechInputError =
  | 'not-supported'
  | 'not-allowed'
  | 'no-speech'
  | 'network'
  | 'unknown'

export function speechErrorMessage(error: SpeechInputError): string {
  switch (error) {
    case 'not-supported':
      return '当前浏览器不支持语音输入，请使用 Chrome / Edge，或切换为文字输入。'
    case 'not-allowed':
      return '未获得麦克风权限，请在浏览器设置中允许访问麦克风。'
    case 'no-speech':
      return '未检测到语音，请靠近麦克风后再试。'
    case 'network':
      return '语音识别需要网络连接，请检查网络后重试。'
    default:
      return '语音识别失败，请稍后重试或改用文字输入。'
  }
}

function getSpeechRecognitionCtor(): SpeechRecognitionConstructor | null {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

export function isSpeechInputSupported(): boolean {
  return getSpeechRecognitionCtor() !== null
}

/** 语音结束口令（说 "over" 停止录音，不写入正文） */
const STOP_COMMAND_RE = /\bover\b/i

export function hasStopCommand(text: string): boolean {
  return STOP_COMMAND_RE.test(text.trim())
}

export function stripStopCommand(text: string): string {
  return text.replace(/\s*\bover\b\.?\s*/gi, ' ').replace(/\s+/g, ' ').trim()
}

export function useSpeechInput(options?: {
  lang?: string
  onFinal?: (text: string) => void
  onInterim?: (text: string) => void
  onStopCommand?: () => void
  onError?: (error: SpeechInputError) => void
}) {
  const supported = isSpeechInputSupported()
  const listening = ref(false)
  const interimText = ref('')
  let recognition: SpeechRecognition | null = null

  function stop() {
    if (recognition) {
      try {
        recognition.stop()
      } catch {
        /* ignore */
      }
      recognition = null
    }
    listening.value = false
    interimText.value = ''
  }

  function start() {
    if (!supported || listening.value) return

    const Ctor = getSpeechRecognitionCtor()
    if (!Ctor) {
      options?.onError?.('not-supported')
      return
    }

    recognition = new Ctor()
    recognition.lang = options?.lang ?? 'zh-CN'
    recognition.continuous = true
    recognition.interimResults = true

    recognition.onresult = (event) => {
      let interim = ''
      let finalChunk = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        const transcript = result[0]?.transcript ?? ''
        if (result.isFinal) {
          finalChunk += transcript
        } else {
          interim += transcript
        }
      }

      const handleChunk = (raw: string, isFinal: boolean) => {
        const shouldStop = hasStopCommand(raw)
        const cleaned = stripStopCommand(raw)
        if (isFinal) {
          interimText.value = ''
          if (cleaned) options?.onFinal?.(cleaned)
        } else {
          interimText.value = cleaned
          options?.onInterim?.(cleaned)
          if (shouldStop) {
            if (cleaned) {
              options?.onFinal?.(cleaned)
              interimText.value = ''
            }
            options?.onStopCommand?.()
            stop()
            return
          }
        }
        if (shouldStop) {
          options?.onStopCommand?.()
          stop()
        }
      }

      if (finalChunk) handleChunk(finalChunk, true)
      else if (interim) handleChunk(interim, false)
    }

    recognition.onerror = (event) => {
      let err: SpeechInputError = 'unknown'
      if (event.error === 'not-allowed') err = 'not-allowed'
      else if (event.error === 'no-speech') err = 'no-speech'
      else if (event.error === 'network') err = 'network'
      options?.onError?.(err)
      stop()
    }

    recognition.onend = () => {
      listening.value = false
      interimText.value = ''
      recognition = null
    }

    try {
      recognition.start()
      listening.value = true
    } catch {
      options?.onError?.('unknown')
      stop()
    }
  }

  function toggle() {
    if (listening.value) stop()
    else start()
  }

  onBeforeUnmount(stop)

  return {
    supported,
    listening,
    interimText,
    start,
    stop,
    toggle,
  }
}
