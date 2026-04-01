import api from './api'
import type {
  DatabaseInfo,
  TableInfo,
  TableSchema,
  QueryResponse,
  DatabaseCreate,
} from '@/types'

export const databaseService = {
  async listDatabases(): Promise<DatabaseInfo[]> {
    const { data } = await api.get<DatabaseInfo[]>('/database/databases')
    return data
  },

  async listTables(dbName: string): Promise<TableInfo[]> {
    const { data } = await api.get<TableInfo[]>(
      `/database/databases/${encodeURIComponent(dbName)}/tables`
    )
    return data
  },

  async getTableSchema(dbName: string, table: string): Promise<TableSchema> {
    const { data } = await api.get<TableSchema>(
      `/database/databases/${encodeURIComponent(dbName)}/tables/${encodeURIComponent(table)}`
    )
    return data
  },

  async executeQuery(dbName: string, sql: string): Promise<QueryResponse> {
    const { data } = await api.post<QueryResponse>(
      `/database/databases/${encodeURIComponent(dbName)}/query`,
      { sql }
    )
    return data
  },

  async createDatabase(payload: DatabaseCreate): Promise<DatabaseInfo> {
    const { data } = await api.post<DatabaseInfo>('/database/databases', payload)
    return data
  },
}
