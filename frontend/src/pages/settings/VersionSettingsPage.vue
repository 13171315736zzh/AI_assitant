<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { VersionInfo } from '@/services/settingsService'
import { checkVersion, fetchVersion } from '@/services/settingsService'

const loading = ref(true)
const checking = ref(false)
const versionInfo = ref<VersionInfo | null>(null)

async function load() {
  loading.value = true
  try {
    const res = await fetchVersion()
    if (res.code === 200) {
      versionInfo.value = res.data
    }
  } finally {
    loading.value = false
  }
}

async function checkUpdate() {
  checking.value = true
  try {
    const res = await checkVersion()
    if (res.code === 200) {
      alert(res.data.message)
    }
  } finally {
    checking.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="settings-page">
    <h1>版本升级</h1>

    <div v-if="loading" class="loading">加载中…</div>
    <template v-else-if="versionInfo">
      <div class="card tonal">
        <div class="version-title">当前版本</div>
        <div class="version-no">v{{ versionInfo.version }}</div>
        <div class="version-date">发布日期：{{ versionInfo.release_date }}</div>
        <button type="button" class="btn-primary" :disabled="checking" @click="checkUpdate">
          {{ checking ? '检查中…' : '检查更新' }}
        </button>
      </div>

      <div class="card">
        <h3>更新日志</h3>
        <div v-for="entry in versionInfo.changelog" :key="entry.version" class="log-item">
          <strong>{{ entry.version }} · {{ entry.date }}</strong>
          <ul>
            <li v-for="(item, idx) in entry.items" :key="idx">{{ item }}</li>
          </ul>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.settings-page h1 {
  font-size: 22px;
  margin-bottom: 24px;
}

.loading {
  color: var(--text-muted);
  font-size: 14px;
}

.card {
  max-width: 560px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 24px;
  margin-bottom: 20px;
}

.card.tonal {
  background: var(--user-bubble-bg);
  border-color: var(--user-bubble-border);
}

.version-title {
  font-size: 13px;
  color: var(--text-secondary);
}

.version-no {
  font-family: 'Outfit', sans-serif;
  font-size: 28px;
  font-weight: 700;
  margin: 8px 0;
}

.version-date {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.card h3 {
  font-size: 16px;
  margin-bottom: 12px;
}

.log-item {
  font-size: 13px;
  color: var(--text-secondary);
}

.log-item ul {
  margin-top: 8px;
  padding-left: 20px;
  line-height: 1.8;
}
</style>
