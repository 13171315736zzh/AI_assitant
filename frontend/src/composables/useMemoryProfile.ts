import { computed, onMounted, ref } from 'vue'
import type { MemoryStructured } from '@/services/settingsService'
import { fetchMemory } from '@/services/settingsService'
import { isGenericAccountLabel } from '@/utils/memorySender'

let cachedProfile: MemoryStructured | null = null
let loadingPromise: Promise<MemoryStructured | null> | null = null

export async function loadMemoryProfile(force = false): Promise<MemoryStructured | null> {
  if (cachedProfile && !force) return cachedProfile
  if (!loadingPromise || force) {
    loadingPromise = fetchMemory()
      .then((res) => {
        if (res.code !== 200) return null
        cachedProfile = res.data.structured
        return cachedProfile
      })
      .catch(() => null)
  }
  return loadingPromise
}

export function invalidateMemoryProfileCache() {
  cachedProfile = null
  loadingPromise = null
}

function pickName(profile: MemoryStructured | null | undefined): string {
  const name = (profile?.display_name ?? '').trim()
  if (name && !isGenericAccountLabel(name)) return name
  return ''
}

function pickEmail(profile: MemoryStructured | null | undefined): string {
  const email = (profile?.email ?? '').trim()
  return email.includes('@') ? email : ''
}

/** 在 OA / 邮件等页面统一读取长期记忆回填姓名、邮箱、工号等。 */
export function useMemoryProfile() {
  const profile = ref<MemoryStructured | null>(cachedProfile)
  const ready = ref(Boolean(cachedProfile))

  onMounted(async () => {
    if (cachedProfile) {
      profile.value = cachedProfile
      ready.value = true
      return
    }
    profile.value = await loadMemoryProfile()
    ready.value = true
  })

  const displayName = computed(() => pickName(profile.value))
  const email = computed(() => pickEmail(profile.value))
  const employeeId = computed(() => (profile.value?.employee_id ?? '').trim())
  const department = computed(() => (profile.value?.department ?? '').trim())
  const baseLocation = computed(() => (profile.value?.base_location ?? '').trim())
  const idNumber = computed(() => (profile.value?.id_number ?? '').trim())
  const jobRole = computed(() => (profile.value?.job_role ?? '').trim())
  const position = computed(() => (profile.value?.position ?? '').trim())
  const travelModePreference = computed(
    () => (profile.value?.travel_mode_preference ?? '').trim(),
  )

  /** 优先长期记忆姓名，其次账号名（非占位），最后 fallback */
  function resolveDisplayName(accountName?: string | null, fallback = '员工'): string {
    return displayName.value
      || (accountName && !isGenericAccountLabel(accountName) ? accountName : '')
      || fallback
  }

  return {
    profile,
    ready,
    displayName,
    email,
    employeeId,
    department,
    baseLocation,
    idNumber,
    jobRole,
    position,
    travelModePreference,
    resolveDisplayName,
    reload: () => loadMemoryProfile(true).then((value) => {
      profile.value = value
      return value
    }),
  }
}
