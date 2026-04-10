export default function TasksRouteLoading() {
  return (
    <main className="space-y-6 pb-3" aria-busy="true" aria-live="polite">
      <section className="nexus-panel animate-pulse p-6">
        <div className="h-4 w-36 rounded bg-[#ece6d9]" />
        <div className="mt-3 h-8 w-56 rounded bg-[#ece6d9]" />
        <div className="mt-3 h-4 w-full max-w-3xl rounded bg-[#f2ece1]" />
      </section>
      <section className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-4">
          <div className="nexus-panel min-h-[220px] animate-pulse p-4" />
          <div className="nexus-panel min-h-[180px] animate-pulse p-4" />
        </div>
        <div className="nexus-panel min-h-[520px] animate-pulse p-4" />
      </section>
    </main>
  );
}

