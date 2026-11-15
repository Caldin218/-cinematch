import { useQuery } from '@tanstack/react-query'
import { getReadiness } from '../lib/api'
import { useUiStore } from '../store/ui'

export function HealthPage() {
  const { autoRefresh, toggleAutoRefresh } = useUiStore()
  const health = useQuery({ queryKey: ['health', 'ready'], queryFn: getReadiness,
    refetchInterval: autoRefresh ? 10000 : false, retry: 1 })

  return <main className="mx-auto max-w-3xl px-6 py-20">
    <p className="text-sm font-semibold uppercase tracking-widest text-amber-400">CineMatch / Foundation</p>
    <h1 className="mt-4 text-4xl font-bold">System health</h1>
    <p className="mt-4 text-slate-300">Connection status for the API, PostgreSQL and Redis.</p>
    <section aria-live="polite" className="mt-8 rounded-xl border border-slate-700 bg-slate-900 p-6">
      {health.isPending && <p>Checking services…</p>}
      {health.isError && <p role="alert">The API could not be reached. Check that the backend is running.</p>}
      {health.data && <>
        <h2 className="text-xl font-semibold">{health.data.status === 'ready' ? 'All services ready' : 'Services need attention'}</h2>
        <dl className="mt-4 space-y-3">
          <div className="flex justify-between"><dt>API</dt><dd>reachable</dd></div>
          {Object.entries(health.data.checks).map(([name, status]) =>
            <div key={name} className="flex justify-between"><dt>{name}</dt><dd>{status}</dd></div>)}
        </dl>
        {health.isError && <p className="mt-4">The values above are from the last successful check.</p>}
      </>}
    </section>
    <div className="mt-6 flex flex-wrap items-center gap-6">
      <button onClick={() => void health.refetch()} disabled={health.isFetching}
        className="rounded bg-amber-400 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-amber-300">
        {health.isFetching ? 'Checking…' : 'Check again'}
      </button>
      <label className="flex items-center gap-2"><input type="checkbox" checked={autoRefresh} onChange={toggleAutoRefresh} />Refresh every 10 seconds</label>
    </div>
  </main>
}
