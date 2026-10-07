/**
 * Minimal in-memory stand-in for the supabase-js query builder.
 *
 * Reads: `from(table)` resolves to the canned rows for that table no matter which
 * filters are chained (the code under test does its own filtering in JS, and
 * where it doesn't, tests seed only the rows the filter would return).
 * Writes: update/insert/delete are recorded in `calls` for assertions.
 */
export type Row = Record<string, unknown>

export interface RecordedCall {
  table: string
  op: "select" | "update" | "insert" | "delete"
  payload?: unknown
  filters: [string, unknown][]
}

export function createFakeSupabase(tables: Record<string, Row[]> = {}) {
  const calls: RecordedCall[] = []

  function from(table: string) {
    const call: RecordedCall = { table, op: "select", filters: [] }
    let single = false
    const builder = {
      select: () => builder,
      update: (payload: unknown) => ((call.op = "update"), (call.payload = payload), builder),
      insert: (payload: unknown) => ((call.op = "insert"), (call.payload = payload), builder),
      delete: () => ((call.op = "delete"), builder),
      eq: (col: string, val: unknown) => (call.filters.push([col, val]), builder),
      is: () => builder,
      like: () => builder,
      order: () => builder,
      limit: () => builder,
      single: () => ((single = true), builder),
      then(resolve: (v: { data: unknown; error: null }) => unknown, reject?: (e: unknown) => unknown) {
        calls.push(call)
        let data: unknown = null
        if (call.op === "select") {
          const rows = tables[table] ?? []
          data = single ? rows[0] ?? null : rows
        }
        return Promise.resolve({ data, error: null }).then(resolve, reject)
      },
    }
    return builder
  }

  return { client: { from }, calls }
}
