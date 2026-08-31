'use client'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html>
      <body className="flex min-h-screen flex-col items-center justify-center p-4 bg-slate-50 font-sans">
        <div className="max-w-md w-full p-6 bg-white rounded-2xl shadow-lg border border-slate-100 text-center">
          <h2 className="text-xl font-bold text-slate-800 mb-2">Algo deu errado</h2>
          <p className="text-sm text-slate-500 mb-4">{error?.message || 'Ocorreu um erro inesperado.'}</p>
          <button
            onClick={() => reset()}
            className="px-4 py-2 bg-slate-900 text-white text-sm font-semibold rounded-xl hover:bg-slate-800 transition-colors"
          >
            Tentar novamente
          </button>
        </div>
      </body>
    </html>
  )
}
