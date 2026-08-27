<script setup lang="ts">
function checkUpdate() {
  alert('已是最新版本')
}
</script>

<template>
  <div class="settings-page">
    <h1>版本升级</h1>
    <div class="card tonal">
      <div class="version-title">当前版本</div>
      <div class="version-no">v1.0.0</div>
      <div class="version-date">发布日期：2026-03-20</div>
      <button type="button" class="btn-primary" @click="checkUpdate">检查更新</button>
    </div>

    <div class="card">
      <h3>更新日志</h3>
      <div class="log-item">
        <strong>v1.0.0 · 2026-03-20</strong>
        <ul>
          <li>首次发布：对话、知识库、差旅/工包/会议/邮件工具</li>
          <li>支持个人设置与长期记忆</li>
          <li>人工协助工单</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page h1 {
  font-size: 22px;
  margin-bottom: 24px;
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
  background: #fdf2f2;
  border-color: #f5c6c6;
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
