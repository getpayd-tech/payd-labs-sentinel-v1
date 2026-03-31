// Auth
export interface User {
  id: string
  username: string
  role: string
  created_at: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

// Dashboard — matches backend DashboardStats schema exactly
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

// Services — matches backend ContainerDetail schema
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

// System — matches backend SystemMetrics schema
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
