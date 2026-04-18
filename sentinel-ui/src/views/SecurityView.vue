<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { securityService } from '@/services/security'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Input from '@/components/ui/Input.vue'
import { useToast } from 'vue-toastification'
import { relativeTime } from '@/utils/formatters'
import {
  Shield,
  RefreshCw,
  Ban,
  Unlock,
  Search,
  ActivitySquare,
  LayoutDashboard,
  TriangleAlert,
  UserCheck,
  Info,
} from 'lucide-vue-next'

const queryClient = useQueryClient()
const toast = useToast()

type Tab = 'overview' | 'banned' | 'activity' | 'lookup'
const activeTab = ref<Tab>('overview')

const jailName = ref('sshd')
const banInput = ref('')
const lookupIp = ref('')
const lookupSubmitted = ref('')

// -- Queries --

const { data: jailList } = useQuery({
  queryKey: ['security-jails'],
  queryFn: () => securityService.listJails(),
})

const { data: jail, isLoading: jailLoading, refetch: refetchJail } = useQuery({
  queryKey: ['security-jail', jailName],
  queryFn: () => securityService.getJail(jailName.value),
  refetchInterval: 15000,
})

const { data: stats } = useQuery({
  queryKey: ['security-auth-stats'],
  queryFn: () => securityService.authStats(24),
  refetchInterval: 30000,
})

const { data: activity, refetch: refetchActivity } = useQuery({
  queryKey: ['security-activity'],
  queryFn: () => securityService.activity(100),
  refetchInterval: 10000,
  enabled: computed(() => activeTab.value === 'activity'),
})

const { data: authLog, refetch: refetchAuth } = useQuery({
  queryKey: ['security-auth-log'],
  queryFn: () => securityService.authLog(100),
  refetchInterval: 10000,
  enabled: computed(() => activeTab.value === 'activity'),
})

const { data: ipHistory, isLoading: ipLoading } = useQuery({
  queryKey: ['security-ip-history', lookupSubmitted],
  queryFn: () => securityService.ipHistory(lookupSubmitted.value),
  enabled: computed(() => !!lookupSubmitted.value),
})

// -- Mutations --

const banMutation = useMutation({
  mutationFn: ({ jail, ip }: { jail: string; ip: string }) => securityService.banIp(jail, ip),
  onSuccess: (_d, vars) => {
    toast.success(`Banned ${vars.ip}`)
    banInput.value = ''
    queryClient.invalidateQueries({ queryKey: ['security-jail'] })
  },
  onError: (e: any) => toast.error(e.response?.data?.detail || 'Ban failed'),
})

const unbanMutation = useMutation({
  mutationFn: ({ jail, ip }: { jail: string; ip: string }) => securityService.unbanIp(jail, ip),
  onSuccess: (_d, vars) => {
    toast.success(`Unbanned ${vars.ip}`)
    queryClient.invalidateQueries({ queryKey: ['security-jail'] })
    queryClient.invalidateQueries({ queryKey: ['security-ip-history'] })
  },
  onError: (e: any) => toast.error(e.response?.data?.detail || 'Unban failed'),
})

function submitBan() {
  const ip = banInput.value.trim()
  if (!ip) return
  banMutation.mutate({ jail: jailName.value, ip })
}

function submitLookup() {
  const ip = lookupIp.value.trim()
  if (ip) lookupSubmitted.value = ip
}

function eventVariant(ev: string): 'success' | 'warning' | 'error' | 'neutral' {
  if (ev === 'success') return 'success'
  if (ev === 'failure') return 'error'
  return 'neutral'
}

function actionVariant(action: string | null): 'success' | 'warning' | 'error' | 'neutral' {
  if (!action) return 'neutral'
  if (action === 'Ban' || action === 'Restore Ban') return 'error'
  if (action === 'Unban') return 'success'
  if (action === 'Found') return 'warning'
  return 'neutral'
}

function refreshAll() {
  refetchJail()
  refetchActivity()
  refetchAuth()
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Security"
      description="Monitor SSH access, review fail2ban activity, and manage banned IPs"
    >
      <template #actions>
        <Button variant="outline" size="sm" @click="refreshAll">
          <RefreshCw class="w-4 h-4" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <!-- Tabs -->
    <div class="flex gap-1 mb-4 border-b border-border">
      <button
        v-for="tab in [
          { id: 'overview', label: 'Overview', icon: LayoutDashboard },
          { id: 'banned', label: 'Banned IPs', icon: Ban },
          { id: 'activity', label: 'Activity', icon: ActivitySquare },
          { id: 'lookup', label: 'IP Lookup', icon: Search },
        ]"
        :key="tab.id"
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors border-b-2"
        :class="activeTab === tab.id
          ? 'border-accent text-text'
          : 'border-transparent text-text-secondary hover:text-text'"
        @click="activeTab = tab.id as Tab"
      >
        <component :is="tab.icon" class="w-4 h-4" />
        {{ tab.label }}
      </button>
    </div>

    <!-- OVERVIEW TAB -->
    <div v-if="activeTab === 'overview'" class="space-y-4">
      <!-- Jail cards -->
      <div v-if="jail" class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="card p-5">
          <div class="flex items-center gap-2 text-xs text-text-tertiary mb-2">
            <Shield class="w-4 h-4" />
            Currently banned ({{ jail.name }})
          </div>
          <p class="text-3xl font-heading font-bold text-text">{{ jail.currently_banned }}</p>
          <p class="text-xs text-text-secondary mt-1">{{ jail.total_banned }} total over lifetime</p>
        </div>
        <div class="card p-5">
          <div class="flex items-center gap-2 text-xs text-text-tertiary mb-2">
            <TriangleAlert class="w-4 h-4" />
            Currently failed attempts
          </div>
          <p class="text-3xl font-heading font-bold text-text">{{ jail.currently_failed }}</p>
          <p class="text-xs text-text-secondary mt-1">{{ jail.total_failed }} total over lifetime</p>
        </div>
        <div class="card p-5" v-if="stats">
          <div class="flex items-center gap-2 text-xs text-text-tertiary mb-2">
            <UserCheck class="w-4 h-4" />
            Last 24 hours
          </div>
          <div class="flex items-baseline gap-3">
            <span class="text-2xl font-heading font-bold text-text">{{ stats.successes }}</span>
            <span class="text-xs text-text-secondary">successes</span>
          </div>
          <div class="flex items-baseline gap-3 mt-1">
            <span class="text-sm font-heading font-bold text-red-500">{{ stats.failures }}</span>
            <span class="text-xs text-text-secondary">failures from {{ stats.unique_ips }} IPs</span>
          </div>
        </div>
      </div>

      <!-- Top attackers -->
      <div v-if="stats && stats.top_attackers.length > 0" class="card p-5">
        <h3 class="text-sm font-heading font-semibold text-text mb-3">
          Top attackers (last {{ stats.window_hours }}h)
        </h3>
        <div class="space-y-2">
          <div
            v-for="t in stats.top_attackers"
            :key="t.ip"
            class="flex items-center justify-between p-2 rounded-lg hover:bg-surface-tertiary transition-colors"
          >
            <div class="flex items-center gap-3">
              <span class="text-sm font-mono text-text">{{ t.ip }}</span>
              <Badge variant="error" size="sm">{{ t.failures }} failures</Badge>
            </div>
            <button
              class="text-xs text-accent hover:underline"
              @click="lookupIp = t.ip; submitLookup(); activeTab = 'lookup'"
            >
              View history
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- BANNED IPs TAB -->
    <div v-if="activeTab === 'banned'" class="space-y-4">
      <!-- Ban form -->
      <div class="card p-5">
        <h3 class="text-sm font-heading font-semibold text-text mb-3">Ban an IP</h3>
        <div class="flex items-end gap-2">
          <div class="flex-1">
            <Input v-model="banInput" label="IP address" placeholder="1.2.3.4" @keyup.enter="submitBan" />
          </div>
          <div class="w-40">
            <label class="block text-xs font-medium text-text-secondary mb-1.5">Jail</label>
            <select
              v-model="jailName"
              class="w-full h-10 px-3 text-sm rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
            >
              <option v-for="j in jailList?.jails || []" :key="j" :value="j">{{ j }}</option>
            </select>
          </div>
          <Button variant="accent" size="md" :loading="banMutation.isPending.value" @click="submitBan">
            <Ban class="w-4 h-4" /> Ban
          </Button>
        </div>
      </div>

      <!-- Banned list -->
      <div class="card overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-border">
          <h3 class="text-sm font-heading font-semibold text-text">
            {{ jail?.currently_banned || 0 }} currently banned in {{ jailName }}
          </h3>
        </div>
        <div v-if="jailLoading" class="p-8 text-center text-sm text-text-tertiary">Loading...</div>
        <div v-else-if="!jail || jail.banned_ips.length === 0" class="p-12 text-center">
          <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-surface-tertiary flex items-center justify-center">
            <Shield class="w-7 h-7 text-gray-400" />
          </div>
          <p class="text-sm text-text-secondary">No banned IPs in {{ jailName }}.</p>
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-border">
                <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">IP Address</th>
                <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="ip in jail.banned_ips"
                :key="ip"
                class="border-b border-border last:border-0 hover:bg-surface-secondary transition-colors"
              >
                <td class="px-4 py-3">
                  <span class="text-sm font-mono text-text">{{ ip }}</span>
                </td>
                <td class="px-4 py-3">
                  <div class="flex gap-2">
                    <button
                      class="text-xs text-accent hover:underline"
                      @click="lookupIp = ip; submitLookup(); activeTab = 'lookup'"
                    >
                      History
                    </button>
                    <button
                      class="text-xs text-green-500 hover:underline"
                      :disabled="unbanMutation.isPending.value"
                      @click="unbanMutation.mutate({ jail: jailName, ip })"
                    >
                      <Unlock class="w-3 h-3 inline" /> Unban
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ACTIVITY TAB -->
    <div v-if="activeTab === 'activity'" class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- fail2ban activity -->
      <div class="card overflow-hidden">
        <div class="p-4 border-b border-border">
          <h3 class="text-sm font-heading font-semibold text-text">fail2ban log</h3>
        </div>
        <div class="max-h-[600px] overflow-y-auto">
          <div v-if="!activity || activity.length === 0" class="p-8 text-center text-sm text-text-tertiary">
            No recent fail2ban activity.
          </div>
          <div v-else>
            <div
              v-for="(ev, i) in activity"
              :key="i"
              class="flex items-start gap-3 p-3 border-b border-border last:border-0 text-xs"
            >
              <span class="text-text-tertiary font-mono whitespace-nowrap">{{ relativeTime(ev.timestamp) }}</span>
              <Badge v-if="ev.action" :variant="actionVariant(ev.action)" size="sm">{{ ev.action }}</Badge>
              <span v-if="ev.ip" class="font-mono text-text">{{ ev.ip }}</span>
              <span class="text-text-secondary flex-1 break-all">{{ ev.message }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- SSH auth log -->
      <div class="card overflow-hidden">
        <div class="p-4 border-b border-border">
          <h3 class="text-sm font-heading font-semibold text-text">SSH auth log</h3>
        </div>
        <div class="max-h-[600px] overflow-y-auto">
          <div v-if="!authLog || authLog.length === 0" class="p-8 text-center text-sm text-text-tertiary">
            No recent SSH events.
          </div>
          <div v-else>
            <div
              v-for="(ev, i) in authLog"
              :key="i"
              class="flex items-start gap-3 p-3 border-b border-border last:border-0 text-xs"
            >
              <span class="text-text-tertiary font-mono whitespace-nowrap">{{ relativeTime(ev.timestamp) }}</span>
              <Badge :variant="eventVariant(ev.event)" size="sm">{{ ev.detail }}</Badge>
              <span v-if="ev.ip" class="font-mono text-text">{{ ev.ip }}</span>
              <span v-if="ev.user" class="text-text-secondary">user={{ ev.user }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- IP LOOKUP TAB -->
    <div v-if="activeTab === 'lookup'" class="space-y-4">
      <div class="card p-5">
        <h3 class="text-sm font-heading font-semibold text-text mb-3">Look up an IP</h3>
        <div class="flex items-end gap-2">
          <div class="flex-1">
            <Input v-model="lookupIp" placeholder="1.2.3.4" @keyup.enter="submitLookup" />
          </div>
          <Button variant="accent" size="md" @click="submitLookup">
            <Search class="w-4 h-4" /> Lookup
          </Button>
        </div>
      </div>

      <div v-if="lookupSubmitted && ipLoading" class="card p-8 text-center text-sm text-text-tertiary">
        Loading history for {{ lookupSubmitted }}...
      </div>

      <div v-else-if="ipHistory" class="space-y-4">
        <div class="card p-5 flex items-center justify-between">
          <div>
            <p class="text-xs text-text-tertiary">IP Address</p>
            <p class="text-lg font-mono font-semibold text-text mt-1">{{ ipHistory.ip }}</p>
          </div>
          <div class="flex gap-2">
            <Button
              v-if="jail && jail.banned_ips.includes(ipHistory.ip)"
              variant="outline"
              size="sm"
              @click="unbanMutation.mutate({ jail: jailName, ip: ipHistory.ip })"
            >
              <Unlock class="w-4 h-4" /> Unban
            </Button>
            <Button
              v-else
              variant="outline"
              size="sm"
              @click="banMutation.mutate({ jail: jailName, ip: ipHistory.ip })"
            >
              <Ban class="w-4 h-4" /> Ban
            </Button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div class="card overflow-hidden">
            <div class="p-4 border-b border-border">
              <h3 class="text-sm font-heading font-semibold text-text">
                fail2ban events ({{ ipHistory.fail2ban_events.length }})
              </h3>
            </div>
            <div class="max-h-96 overflow-y-auto">
              <div v-if="ipHistory.fail2ban_events.length === 0" class="p-6 text-center text-xs text-text-tertiary">None</div>
              <div
                v-for="(ev, i) in ipHistory.fail2ban_events"
                :key="i"
                class="flex items-start gap-3 p-3 border-b border-border last:border-0 text-xs"
              >
                <span class="text-text-tertiary whitespace-nowrap">{{ relativeTime(ev.timestamp) }}</span>
                <Badge v-if="ev.action" :variant="actionVariant(ev.action)" size="sm">{{ ev.action }}</Badge>
                <span v-if="ev.jail" class="text-text-secondary">[{{ ev.jail }}]</span>
              </div>
            </div>
          </div>

          <div class="card overflow-hidden">
            <div class="p-4 border-b border-border">
              <h3 class="text-sm font-heading font-semibold text-text">
                SSH events ({{ ipHistory.auth_events.length }})
              </h3>
            </div>
            <div class="max-h-96 overflow-y-auto">
              <div v-if="ipHistory.auth_events.length === 0" class="p-6 text-center text-xs text-text-tertiary">None</div>
              <div
                v-for="(ev, i) in ipHistory.auth_events"
                :key="i"
                class="flex items-start gap-3 p-3 border-b border-border last:border-0 text-xs"
              >
                <span class="text-text-tertiary whitespace-nowrap">{{ relativeTime(ev.timestamp) }}</span>
                <Badge :variant="eventVariant(ev.event)" size="sm">{{ ev.detail }}</Badge>
                <span v-if="ev.user" class="text-text-secondary">user={{ ev.user }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="!lookupSubmitted" class="card p-8 text-center">
        <Info class="w-6 h-6 mx-auto mb-2 text-text-tertiary" />
        <p class="text-sm text-text-secondary">Enter an IP address to see its full activity history.</p>
      </div>
    </div>
  </div>
</template>
