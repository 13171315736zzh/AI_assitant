<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import {
  speechErrorMessage,
  useSpeechInput,
  type SpeechInputError,
} from '@/composables/useSpeechInput'

type InputMode = 'text' | 'voice'

const props = defineProps<{
  disabled?: boolean
  sending?: boolean
}>()

const emit = defineEmits<{
  send: [content: string]
}>()

const text = defineModel<string>({ default: '' })

const inputMode = ref<InputMode>('text')
const textInputRef = ref<HTMLTextAreaElement | null>(null)
const speechError = ref<string | null>(null)
const stoppedByCommand = ref(false)

const speech = useSpeechInput({
  lang: 'zh-CN',
  onFinal: (chunk) => {
    appendSpeechText(chunk)
  },
  onStopCommand: () => {
    stoppedByCommand.value = true
  },
  onError: (error: SpeechInputError) => {
    speechError.value = speechErrorMessage(error)
  },
})

const canSend = computed(() => Boolean(text.value.trim()) && !props.sending && !props.disabled)

function appendSpeechText(chunk: string) {
  const trimmed = chunk.trim()
  if (!trimmed) return
  const base = text.value.trimEnd()
  text.value = base ? `${base} ${trimmed}` : trimmed
}

function submit() {
  if (!text.value.trim() || props.disabled || props.sending) return
  speech.stop()
  emit('send', text.value)
  text.value = ''
  speechError.value = null
  stoppedByCommand.value = false
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}

async function focusInput() {
  inputMode.value = 'text'
  await nextTick()
  textInputRef.value?.focus()
}

defineExpose({ focusInput })

function switchMode(mode: InputMode) {
  if (props.disabled) return
  if (mode === inputMode.value) return
  speech.stop()
  speechError.value = null
  stoppedByCommand.value = false
  inputMode.value = mode
}

function handleVoiceToggle() {
  if (props.disabled) return
  if (!speech.supported) {
    speechError.value = speechErrorMessage('not-supported')
    return
  }
  speechError.value = null
  stoppedByCommand.value = false
  speech.toggle()
}

watch(
  () => props.disabled,
  (ended) => {
    if (ended) speech.stop()
  },
)

watch(
  () => speech.listening.value,
  (listening, wasListening) => {
    if (wasListening && !listening && stoppedByCommand.value) {
      stoppedByCommand.value = false
    }
  },
)
</script>

<template>
  <div class="input-area">
    <div v-if="disabled" class="ended-hint">当前会话已结束，无法发送新消息</div>

    <div class="mode-bar" :class="{ disabled }">
      <button
        type="button"
        class="mode-btn"
        :class="{ active: inputMode === 'text' }"
        :disabled="disabled"
        @click="switchMode('text')"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="M7 9h10M7 13h6" />
        </svg>
        文字输入
      </button>
      <button
        type="button"
        class="mode-btn"
        :class="{ active: inputMode === 'voice' }"
        :disabled="disabled"
        @click="switchMode('voice')"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M12 1a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4M8 22h8" />
        </svg>
        语音输入
      </button>
    </div>

    <div
      class="input-box"
      :class="{
        disabled,
        sending,
        listening: inputMode === 'voice' && speech.listening.value,
      }"
    >
      <!-- 文字模式 -->
      <template v-if="inputMode === 'text'">
        <textarea
          ref="textInputRef"
          v-model="text"
          rows="1"
          :disabled="disabled"
          placeholder="输入您的需求，例如：下周出差订机票并预约会议室"
          @keydown="onKeydown"
        />
      </template>

      <!-- 语音模式：识别结果写入可编辑文本框 -->
      <template v-else>
        <div class="voice-panel">
          <div class="voice-editor">
            <textarea
              v-model="text"
              rows="2"
              class="voice-textarea"
              :disabled="disabled"
              placeholder="点击麦克风说话，识别结果会出现在这里，您可直接修改"
              @keydown="onKeydown"
            />
            <p v-if="speech.interimText.value" class="interim-preview">
              <span class="interim-label">识别中</span>
              {{ speech.interimText.value }}
            </p>
          </div>

          <button
            type="button"
            class="btn-mic"
            :class="{ active: speech.listening.value, unsupported: !speech.supported }"
            :disabled="disabled"
            :aria-label="speech.listening.value ? '停止录音' : '开始录音'"
            :title="speech.supported ? (speech.listening.value ? '点击停止，或说 over' : '点击开始说话') : '当前浏览器不支持'"
            @click="handleVoiceToggle"
          >
            <span v-if="speech.listening.value" class="mic-pulse" aria-hidden="true" />
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 1a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4M8 22h8" />
            </svg>
          </button>
        </div>
      </template>

      <button
        type="button"
        class="btn-send"
        :disabled="!canSend"
        aria-label="发送"
        @click="submit"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
        </svg>
      </button>
    </div>

    <p v-if="sending && !disabled" class="sending-hint">
      正在处理回复，您可继续输入；完成后再次点击发送
    </p>
    <p v-if="speechError" class="speech-error">{{ speechError }}</p>
    <p v-else-if="inputMode === 'voice' && speech.listening.value" class="speech-hint">
      正在识别… 说 <strong>over</strong> 结束录音，或在文本框中直接修改，确认后点发送
    </p>
    <p v-else-if="inputMode === 'voice' && !speech.supported" class="speech-hint muted">
      语音输入需 Chrome / Edge 浏览器；您也可切换回「文字输入」
    </p>
    <p v-else-if="inputMode === 'voice'" class="speech-hint muted">
      识别内容可自由编辑；录音时说 <strong>over</strong> 可结束当前录制
    </p>
  </div>
</template>

<style scoped>
.input-area {
  padding: 16px 24px 24px;
  background: var(--bg);
  flex-shrink: 0;
}

.ended-hint {
  font-size: 13px;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  margin-bottom: 12px;
  text-align: center;
}

.mode-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.mode-bar.disabled {
  opacity: 0.6;
  pointer-events: none;
}

.mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.mode-btn svg {
  width: 16px;
  height: 16px;
}

.mode-btn:hover:not(:disabled) {
  border-color: #f0b4b4;
  color: var(--primary);
}

.mode-btn.active {
  border-color: var(--primary);
  background: #fdf2f2;
  color: var(--primary);
  font-weight: 600;
}

.input-box {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-box.listening {
  border-color: #f87171;
  box-shadow: 0 0 0 3px rgba(196, 30, 58, 0.1);
}

.input-box.disabled {
  opacity: 0.6;
}

.input-box.sending:not(.disabled) {
  border-color: color-mix(in srgb, var(--primary) 35%, var(--border));
}

.input-box textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.5;
  min-height: 44px;
  color: var(--text);
  background: transparent;
}

.input-box textarea::placeholder {
  color: var(--text-muted);
}

.voice-panel {
  flex: 1;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  min-height: 44px;
}

.voice-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.voice-textarea {
  width: 100%;
  min-height: 52px;
  padding: 8px 10px;
  border: 1px dashed #e2e8f0;
  border-radius: var(--radius-sm);
  background: #f8fafc;
  resize: vertical;
}

.voice-textarea:focus {
  border-color: #f0b4b4;
  background: #fff;
}

.voice-textarea:disabled {
  opacity: 0.7;
}

.interim-preview {
  margin: 0;
  padding: 4px 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-muted);
  word-break: break-word;
}

.interim-label {
  display: inline-block;
  margin-right: 6px;
  padding: 0 6px;
  border-radius: 4px;
  background: #fdf2f2;
  color: var(--primary);
  font-size: 11px;
  font-weight: 600;
}

.btn-mic {
  position: relative;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}

.btn-mic svg {
  width: 20px;
  height: 20px;
  position: relative;
  z-index: 1;
}

.btn-mic:hover:not(:disabled) {
  border-color: #f0b4b4;
  color: var(--primary);
}

.btn-mic.active {
  border-color: var(--primary);
  background: #fdf2f2;
  color: var(--primary);
}

.btn-mic.unsupported {
  opacity: 0.45;
  cursor: not-allowed;
}

.mic-pulse {
  position: absolute;
  inset: -4px;
  border-radius: 999px;
  border: 2px solid var(--primary);
  animation: mic-pulse 1.2s ease-out infinite;
}

@keyframes mic-pulse {
  0% {
    transform: scale(0.92);
    opacity: 0.8;
  }
  100% {
    transform: scale(1.15);
    opacity: 0;
  }
}

.btn-send {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.btn-send:hover:not(:disabled) {
  background: var(--accent);
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-send svg {
  width: 20px;
  height: 20px;
}

.sending-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.speech-error {
  margin: 8px 0 0;
  font-size: 12px;
  color: #b45309;
  line-height: 1.5;
}

.speech-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--primary);
  line-height: 1.5;
}

.speech-hint.muted {
  color: var(--text-muted);
}

.speech-hint strong {
  font-weight: 600;
  color: var(--primary);
}
</style>
