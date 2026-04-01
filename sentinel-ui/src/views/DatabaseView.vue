<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { databaseService } from '@/services/database'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Input from '@/components/ui/Input.vue'
import Modal from '@/components/ui/Modal.vue'
import { useToast } from 'vue-toastification'
import type { DatabaseInfo } from '@/types'
import {
  Database,
  Table2,
  ChevronRight,
  Plus,
  Play,
  RefreshCw,
  Clock,
  AlertCircle,
  Columns3,
} from 'lucide-vue-next'

const queryClient = useQueryClient()
const toast = useToast()

const selectedDb = ref<string | null>(null)
const selectedTable = ref<string | null>(null)
const showCreateModal = ref(false)
const newDbName = ref('')
const newDbPassword = ref('')
const sqlQuery = ref('')
const queryResultRef = ref<HTMLDivElement | null>(null)

// Databases list
const { data: databases, isLoading: dbLoading, isError: dbError } = useQuery({
  queryKey: ['databases'],
  queryFn: () => databaseService.listDatabases(),
})

// Tables for selected database
const { data: tables, isLoading: tablesLoading } = useQuery({
  queryKey: ['tables', selectedDb],
  queryFn: () => databaseService.listTables(selectedDb.value!),
  enabled: computed(() => !!selectedDb.value),
})

// Schema for selected table
const { data: schema, isLoading: schemaLoading } = useQuery({
  queryKey: ['table-schema', selectedDb, selectedTable],
  queryFn: () => databaseService.getTableSchema(selectedDb.value!, selectedTable.value!),
  enabled: computed(() => !!selectedDb.value && !!selectedTable.value),
})

// Query execution
const queryMutation = useMutation({
  mutationFn: (sql: string) => databaseService.executeQuery(selectedDb.value!, sql),
  onSuccess: async () => {
    await nextTick()
    if (queryResultRef.value) {
      queryResultRef.value.scrollTop = 0
    }
  },
  onError: () => {
    // Error is displayed inline via queryMutation.error
  },
})

// Create database
const createDbMutation = useMutation({
  mutationFn: () => databaseService.createDatabase({ name: newDbName.value, password: newDbPassword.value }),
  onSuccess: (db) => {
    toast.success(`Database "${db.name}" created`)
    showCreateModal.value = false
    newDbName.value = ''
    newDbPassword.value = ''
    queryClient.invalidateQueries({ queryKey: ['databases'] })
  },
  onError: (e: any) => {
    toast.error(e.response?.data?.detail || 'Failed to create database')
  },
})

function selectDatabase(db: DatabaseInfo) {
  selectedDb.value = db.name
  selectedTable.value = null
}

function selectTableRow(tableName: string) {
  selectedTable.value = tableName
}

function goToDbList() {
  selectedDb.value = null
  selectedTable.value = null
}

function goToTablesList() {
  selectedTable.value = null
}

function runQuery() {
  if (!sqlQuery.value.trim() || !selectedDb.value) return
  queryMutation.mutate(sqlQuery.value.trim())
}

function openCreateModal() {
  newDbName.value = ''
  newDbPassword.value = ''
  showCreateModal.value = true
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Database"
      description="PostgreSQL database browser and query editor"
    />

    <!-- Loading state -->
    <template v-if="dbLoading">
      <div class="flex gap-4">
        <div class="w-64 shrink-0">
          <div class="card p-4 space-y-3">
            <div class="skeleton h-4 w-24" />
            <div v-for="i in 4" :key="i" class="skeleton h-10 w-full rounded-lg" />
          </div>
        </div>
        <div class="flex-1 card p-8 text-center">
          <div class="skeleton h-4 w-48 mx-auto" />
        </div>
      </div>
    </template>

    <!-- Error state -->
    <div v-else-if="dbError" class="card p-8 text-center">
      <p class="text-text-secondary">Failed to load databases.</p>
    </div>

    <!-- Main layout -->
    <template v-else>
      <div class="flex gap-4" style="min-height: 500px;">
        <!-- Left sidebar: database list -->
        <div class="w-64 shrink-0 flex flex-col">
          <div class="card p-3 flex-1 flex flex-col overflow-hidden">
            <h3 class="text-xs font-semibold text-text-secondary uppercase tracking-wide px-2 mb-2">
              Databases
            </h3>
            <div class="flex-1 overflow-y-auto custom-scrollbar space-y-1">
              <div v-if="databases && databases.length === 0" class="px-2 py-4 text-center">
                <Database class="w-6 h-6 mx-auto text-gray-300 dark:text-gray-600 mb-1" />
                <p class="text-xs text-gray-400">No databases</p>
              </div>
              <button
                v-for="db in databases"
                :key="db.name"
                :class="[
                  'w-full text-left px-3 py-2.5 rounded-lg transition-colors text-sm',
                  selectedDb === db.name
                    ? 'bg-accent/10 text-accent border border-accent/20'
                    : 'hover:bg-gray-50 dark:hover:bg-neutral-800 text-text',
                ]"
                @click="selectDatabase(db)"
              >
                <div class="flex items-center gap-2">
                  <Database class="w-4 h-4 shrink-0" />
                  <span class="font-semibold font-heading truncate">{{ db.name }}</span>
                </div>
                <div class="flex items-center gap-3 mt-1 ml-6 text-2xs text-gray-400 dark:text-gray-500">
                  <span>{{ db.size_pretty }}</span>
                  <span>{{ db.tables_count }} table{{ db.tables_count !== 1 ? 's' : '' }}</span>
                </div>
              </button>
            </div>
            <div class="mt-2 pt-2 border-t border-border">
              <Button variant="outline" size="sm" class="w-full" @click="openCreateModal">
                <Plus class="w-4 h-4" />
                Create Database
              </Button>
            </div>
          </div>
        </div>

        <!-- Main area -->
        <div class="flex-1 flex flex-col gap-4 min-w-0">
          <!-- Breadcrumb -->
          <div class="flex items-center gap-1.5 text-sm">
            <button
              class="text-text-secondary hover:text-kPrimary dark:hover:text-white transition-colors"
              @click="goToDbList"
            >
              Databases
            </button>
            <template v-if="selectedDb">
              <ChevronRight class="w-3.5 h-3.5 text-gray-400" />
              <button
                :class="[
                  'transition-colors',
                  selectedTable
                    ? 'text-text-secondary hover:text-kPrimary dark:hover:text-white'
                    : 'text-text font-semibold',
                ]"
                @click="goToTablesList"
              >
                {{ selectedDb }}
              </button>
            </template>
            <template v-if="selectedTable">
              <ChevronRight class="w-3.5 h-3.5 text-gray-400" />
              <span class="text-text font-semibold">{{ selectedTable }}</span>
            </template>
          </div>

          <!-- No DB selected -->
          <div v-if="!selectedDb" class="card p-12 text-center flex-1 flex items-center justify-center">
            <div>
              <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-surface-tertiary flex items-center justify-center">
                <Database class="w-7 h-7 text-gray-400" />
              </div>
              <h3 class="text-lg font-heading font-semibold text-text mb-2">
                Select a Database
              </h3>
              <p class="text-sm text-text-secondary">
                Choose a database from the sidebar to browse tables and run queries.
              </p>
            </div>
          </div>

          <!-- Tables list (DB selected, no table selected) -->
          <template v-else-if="!selectedTable">
            <div class="card overflow-hidden flex-1">
              <!-- Loading -->
              <div v-if="tablesLoading" class="p-4 space-y-3">
                <div v-for="i in 5" :key="i" class="flex items-center gap-3">
                  <div class="skeleton h-8 w-8 rounded-lg" />
                  <div class="flex-1">
                    <div class="skeleton h-4 w-32 mb-1" />
                    <div class="skeleton h-3 w-20" />
                  </div>
                </div>
              </div>

              <template v-else>
                <div class="overflow-x-auto">
                  <table class="w-full">
                    <thead>
                      <tr class="border-b border-border">
                        <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Table</th>
                        <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Rows</th>
                        <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Size</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="table in tables"
                        :key="table.name"
                        class="border-b border-border last:border-0 hover:bg-surface-secondary cursor-pointer transition-colors"
                        @click="selectTableRow(table.name)"
                      >
                        <td class="px-4 py-3">
                          <div class="flex items-center gap-2.5">
                            <div class="w-8 h-8 rounded-lg bg-surface-tertiary flex items-center justify-center shrink-0">
                              <Table2 class="w-4 h-4 text-text-secondary" />
                            </div>
                            <span class="text-sm font-semibold font-heading text-text">
                              {{ table.name }}
                            </span>
                          </div>
                        </td>
                        <td class="px-4 py-3">
                          <span class="text-sm text-text-secondary">{{ table.row_count.toLocaleString() }}</span>
                        </td>
                        <td class="px-4 py-3">
                          <span class="text-sm text-text-secondary">{{ table.size_pretty }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div v-if="tables && tables.length === 0" class="p-8 text-center">
                  <Table2 class="w-6 h-6 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
                  <p class="text-sm text-text-secondary">No tables in this database.</p>
                </div>
              </template>
            </div>
          </template>

          <!-- Table schema (table selected) -->
          <template v-else>
            <div class="card overflow-hidden flex-1">
              <div v-if="schemaLoading" class="p-4 space-y-3">
                <div v-for="i in 5" :key="i" class="skeleton h-8 w-full rounded-lg" />
              </div>

              <template v-else-if="schema">
                <div class="px-4 py-3 border-b border-border flex items-center gap-2">
                  <Columns3 class="w-4 h-4 text-accent" />
                  <h3 class="text-sm font-semibold font-heading text-text">
                    Columns
                  </h3>
                  <Badge variant="neutral" size="sm">{{ schema.columns.length }}</Badge>
                </div>
                <div class="overflow-x-auto">
                  <table class="w-full">
                    <thead>
                      <tr class="border-b border-border">
                        <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Name</th>
                        <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Type</th>
                        <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Nullable</th>
                        <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Default</th>
                        <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Key</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="col in schema.columns"
                        :key="col.name"
                        class="border-b border-border last:border-0"
                      >
                        <td class="px-4 py-2.5">
                          <span class="text-sm font-mono font-semibold text-text">{{ col.name }}</span>
                        </td>
                        <td class="px-4 py-2.5">
                          <span class="text-sm font-mono text-text-secondary">{{ col.type }}</span>
                        </td>
                        <td class="px-4 py-2.5">
                          <Badge :variant="col.nullable ? 'warning' : 'neutral'" size="sm">
                            {{ col.nullable ? 'YES' : 'NO' }}
                          </Badge>
                        </td>
                        <td class="px-4 py-2.5">
                          <span class="text-sm font-mono text-text-secondary">
                            {{ col.default_value ?? '-' }}
                          </span>
                        </td>
                        <td class="px-4 py-2.5">
                          <Badge v-if="col.is_primary_key" variant="info" size="sm">PK</Badge>
                          <span v-else class="text-sm text-gray-400">-</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
            </div>
          </template>

          <!-- Query editor (bottom panel) -->
          <div v-if="selectedDb" class="card overflow-hidden" style="height: 16rem;">
            <div class="flex items-center justify-between px-4 py-2.5 border-b border-border">
              <h3 class="text-sm font-semibold font-heading text-text">Query Editor</h3>
              <Button
                variant="accent"
                size="xs"
                :loading="queryMutation.isPending.value"
                :disabled="!sqlQuery.trim()"
                @click="runQuery"
              >
                <Play class="w-3.5 h-3.5" />
                Run Query
              </Button>
            </div>
            <div class="flex flex-col" style="height: calc(100% - 41px);">
              <textarea
                v-model="sqlQuery"
                placeholder="SELECT * FROM ... LIMIT 100"
                class="flex-1 w-full px-4 py-3 bg-neutral-950 text-gray-300 font-mono text-xs resize-none focus:outline-none placeholder:text-gray-600 custom-scrollbar"
                @keydown.ctrl.enter="runQuery"
                @keydown.meta.enter="runQuery"
              />
              <!-- Query results -->
              <div
                v-if="queryMutation.data.value || queryMutation.error.value"
                ref="queryResultRef"
                class="border-t border-neutral-800 bg-neutral-950 overflow-auto custom-scrollbar"
                style="max-height: 50%;"
              >
                <!-- Error -->
                <div v-if="queryMutation.error.value" class="px-4 py-3 flex items-center gap-2 text-red-400 text-xs">
                  <AlertCircle class="w-4 h-4 shrink-0" />
                  <span>{{ (queryMutation.error.value as any)?.response?.data?.detail || 'Query execution failed' }}</span>
                </div>

                <!-- Results -->
                <template v-else-if="queryMutation.data.value">
                  <div class="px-4 py-1.5 flex items-center gap-3 text-2xs text-gray-500 border-b border-neutral-800">
                    <span class="flex items-center gap-1">
                      <Clock class="w-3 h-3" />
                      {{ queryMutation.data.value.execution_time_ms }}ms
                    </span>
                    <span>{{ queryMutation.data.value.row_count }} row{{ queryMutation.data.value.row_count !== 1 ? 's' : '' }}</span>
                  </div>
                  <div v-if="queryMutation.data.value.rows.length > 0" class="overflow-x-auto">
                    <table class="w-full">
                      <thead>
                        <tr>
                          <th
                            v-for="col in queryMutation.data.value.columns"
                            :key="col"
                            class="text-left text-2xs font-semibold text-gray-500 uppercase tracking-wide px-3 py-1.5 border-b border-neutral-800 whitespace-nowrap"
                          >
                            {{ col }}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="(row, idx) in queryMutation.data.value.rows"
                          :key="idx"
                          class="border-b border-neutral-800/50 last:border-0"
                        >
                          <td
                            v-for="col in queryMutation.data.value.columns"
                            :key="col"
                            class="px-3 py-1.5 text-xs font-mono text-gray-300 whitespace-nowrap"
                          >
                            {{ row[col] ?? 'NULL' }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-else class="px-4 py-3 text-xs text-gray-500">Query returned no rows.</div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Create Database Modal -->
    <Modal v-model="showCreateModal" title="Create Database" size="md">
      <div class="space-y-4">
        <Input
          v-model="newDbName"
          label="Database Name"
          placeholder="my_database"
        />
        <Input
          v-model="newDbPassword"
          label="Password"
          type="password"
          placeholder="Enter a secure password"
        />
      </div>
      <template #footer>
        <div class="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" @click="showCreateModal = false">Cancel</Button>
          <Button
            variant="accent"
            size="sm"
            :disabled="!newDbName.trim() || !newDbPassword.trim()"
            :loading="createDbMutation.isPending.value"
            @click="createDbMutation.mutate()"
          >
            <Plus class="w-4 h-4" />
            Create
          </Button>
        </div>
      </template>
    </Modal>
  </div>
</template>
