// ─── Auth (Payd Auth multi-step flow) ────────────────────────────────────────

export interface User {
  id: string
  username: string
  email?: string
  is_admin: boolean
  role: string
  created_at: string
}

export interface LoginResponse {
  session_token: string
}

export interface OtpResponse {
  message: string
}

export interface VerifyOtpResponse {
  auth_token: string
  refresh_token: string
}

export interface RefreshResponse {
  auth_token: string
  refresh_token: string
}

export interface JwtPayload {
  sub: string
  username: string
  is_admin: boolean
  exp: number
  iat: number
  [key: string]: unknown
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export interface SystemStats {
  cpu_percent: number
  memory_used_mb: number
  memory_total_mb: number
  memory_percent: number
  disk_used_gb: number
  disk_total_gb: number
  disk_percent: number
  uptime_seconds: number
}

export interface ContainerInfo {
  name: string
  status: string
  health: string | null
  image: string
  created: string
  started_at: string | null
  ports: Record<string, string | null> | null
  cpu_percent: number
  memory_usage_mb: number
  memory_limit_mb: number
  network_rx_mb: number
  network_tx_mb: number
}

export interface DashboardStats {
  total_containers: number
  running_containers: number
  healthy_containers: number
  unhealthy_containers: number
  system: SystemStats
  containers: ContainerInfo[]
}

export interface HealthOverview {
  service_name: string
  status: string
  uptime: string | null
  last_check: string | null
}

// ─── Services (containers) ───────────────────────────────────────────────────

export interface ContainerDetail {
  name: string
  id: string
  status: string
  health: string | null
  image: string
  image_id: string
  created: string
  started_at: string | null
  restart_count: number
  platform: string | null
  ports: Record<string, string | null> | null
  networks: string[]
  volumes: string[]
  env_keys: string[]
  labels: Record<string, string>
  cpu_percent: number
  memory_usage_mb: number
  memory_limit_mb: number
}

export interface ContainerAction {
  success: boolean
  message: string
}

export interface LogEntry {
  timestamp: string
  message: string
  stream: 'stdout' | 'stderr'
}

export interface ContainerLogs {
  container_name: string
  logs: LogEntry[]
  total: number
}

// ─── System ──────────────────────────────────────────────────────────────────

export interface SystemMetrics {
  cpu_percent: number
  cpu_count: number
  memory_used_mb: number
  memory_total_mb: number
  memory_percent: number
  disk_used_gb: number
  disk_total_gb: number
  disk_percent: number
  network_rx_mb: number
  network_tx_mb: number
  uptime_seconds: number
  load_average: number[]
}

export interface MetricsHistoryPoint {
  timestamp: string
  cpu_percent: number
  memory_used_mb: number
  disk_used_gb: number
  container_count: number
}

// ─── Deployments ─────────────────────────────────────────────────────────────

export type DeploymentStatus =
  | 'pending'
  | 'pulling'
  | 'healthy'
  | 'failed'
  | 'rolled_back'

export interface DeploymentInfo {
  id: string
  project_id: string
  project_name: string
  trigger_type: 'manual' | 'webhook' | 'api' | 'schedule'
  image_tag: string
  status: DeploymentStatus
  duration_seconds: number | null
  triggered_by: string
  started_at: string
  finished_at: string | null
  error_message: string | null
  rollback_of: string | null
}

export interface DeploymentList {
  items: DeploymentInfo[]
  total: number
  page: number
  per_page: number
}

export interface DeployRequest {
  image_tag?: string
}

// ─── Projects ────────────────────────────────────────────────────────────────

export type ProjectType = 'fastapi' | 'vue' | 'laravel' | 'static' | 'blended' | 'nuxt' | 'custom'

export interface ProjectInfo {
  id: string
  name: string
  display_name: string
  type: ProjectType
  domain: string | null
  status: string
  container_count: number
  github_repo: string | null
  ghcr_image: string | null
  health_endpoint: string | null
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  display_name: string
  type: ProjectType
  domain?: string
  github_repo?: string
  ghcr_image?: string
  health_endpoint?: string
  env_vars?: Record<string, string>
  database?: {
    name: string
    password: string
  }
}

export interface ProjectUpdate {
  display_name?: string
  domain?: string
  github_repo?: string
  ghcr_image?: string
  health_endpoint?: string
}

export interface TemplateInfo {
  id: string
  name: string
  type: ProjectType
  description: string
  default_health_endpoint: string
  default_port: number
}

export interface EnvVar {
  key: string
  value: string
}

export interface ProvisionRequest {
  env_vars?: Record<string, string>
  database?: {
    name: string
    password: string
  }
}

export interface ScanResult {
  discovered: ProjectInfo[]
  total: number
}

// ─── Database ────────────────────────────────────────────────────────────────

export interface DatabaseInfo {
  name: string
  owner: string
  size_bytes: number
  size_pretty: string
  tables_count: number
  created_at: string | null
}

export interface TableInfo {
  name: string
  row_count: number
  size_pretty: string
  has_primary_key: boolean
}

export interface ColumnSchema {
  name: string
  type: string
  nullable: boolean
  default_value: string | null
  is_primary_key: boolean
}

export interface IndexSchema {
  name: string
  columns: string[]
  is_unique: boolean
  is_primary: boolean
}

export interface TableSchema {
  table_name: string
  columns: ColumnSchema[]
  indexes: IndexSchema[]
  row_count: number
}

export interface QueryResponse {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  execution_time_ms: number
}

export interface DatabaseCreate {
  name: string
  password: string
}

// ─── Domains ─────────────────────────────────────────────────────────────────

export interface UpstreamTarget {
  address: string
  port: number
}

export type TlsMode = 'auto' | 'cloudflare_dns' | 'off'

export interface DomainInfo {
  domain: string
  upstreams: UpstreamTarget[]
  tls_enabled: boolean
  tls_auto: boolean
  tls_mode: TlsMode
  created_at: string | null
}

export interface DomainCreate {
  domain: string
  upstreams: UpstreamTarget[]
  tls_mode?: TlsMode
}

export interface DomainUpdate {
  upstreams?: UpstreamTarget[]
  tls_mode?: TlsMode
}

// ─── Logs (aggregated) ───────────────────────────────────────────────────────

export interface AggregatedLogEntry {
  container: string
  timestamp: string
  message: string
  stream: 'stdout' | 'stderr'
}

export interface AggregatedLogs {
  entries: AggregatedLogEntry[]
  total: number
  containers: string[]
}

export interface LogsParams {
  containers?: string[]
  search?: string
  stream?: 'all' | 'stdout' | 'stderr'
  tail?: number
}

// ─── Audit ───────────────────────────────────────────────────────────────────

export interface AuditEntry {
  id: string
  timestamp: string
  user: string
  action: string
  target: string
  details: string | null
  ip_address: string | null
}

export interface AuditList {
  items: AuditEntry[]
  total: number
  page: number
  per_page: number
}

export interface AuditParams {
  action?: string
  date_from?: string
  date_to?: string
  page?: number
  per_page?: number
}
