'use client'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-4 text-center font-ui">
      <div className="max-w-md w-full p-6 bg-white rounded-2xl shadow-sm border border-slate-100">
        <h2 className="text-xl font-bold text-slate-800 mb-2">Ops! Ocorreu um erro</h2>
        <p className="text-sm text-slate-500 mb-4">{error?.message || 'Não foi possível carregar a página.'}</p>
        <button
          onClick={() => reset()}
          className="px-4 py-2 bg-slate-900 text-white text-sm font-semibold rounded-xl hover:bg-slate-800 transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    </div>
  )
}
