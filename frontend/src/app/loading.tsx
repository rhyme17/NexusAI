export default function RootLoading() {
  return (
    <main className="space-y-6 pb-3" aria-busy="true" aria-live="polite">
      <section className="nexus-panel animate-pulse p-6">
        <div className="h-4 w-28 rounded bg-[#ece6d9]" />
        <div className="mt-3 h-8 w-64 rounded bg-[#ece6d9]" />
        <div className="mt-3 h-4 w-full max-w-2xl rounded bg-[#f2ece1]" />
      </section>
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="nexus-panel min-h-[300px] animate-pulse p-5" />
        <div className="nexus-panel min-h-[300px] animate-pulse p-5" />
      </section>
    </main>
  );
}

