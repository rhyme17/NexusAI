export default function TaskWorkspaceRouteLoading() {
  return (
    <main className="space-y-6 pb-3" aria-busy="true" aria-live="polite">
      <section className="nexus-panel animate-pulse p-6">
        <div className="h-4 w-44 rounded bg-[#ece6d9]" />
        <div className="mt-3 h-8 w-full max-w-2xl rounded bg-[#ece6d9]" />
        <div className="mt-3 h-4 w-full max-w-3xl rounded bg-[#f2ece1]" />
      </section>
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_360px]">
        <div className="nexus-panel min-h-[520px] animate-pulse p-4" />
        <div className="space-y-4">
          <div className="nexus-panel min-h-[180px] animate-pulse p-4" />
          <div className="nexus-panel min-h-[280px] animate-pulse p-4" />
        </div>
      </section>
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="nexus-panel min-h-[280px] animate-pulse p-4" />
        <div className="nexus-panel min-h-[280px] animate-pulse p-4" />
      </section>
    </main>
  );
}

