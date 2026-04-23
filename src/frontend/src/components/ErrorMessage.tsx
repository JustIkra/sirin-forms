interface Props {
  message: string;
  status?: number;
}

export default function ErrorMessage({ message, status }: Props) {
  return (
    <div
      className="mx-auto mt-8 max-w-lg rounded-2xl border border-fact-red/25 bg-fact-red/10 p-5"
      data-testid="error-message"
    >
      <h3 className="text-sm font-semibold uppercase tracking-wider text-fact-red">
        Ошибка{status ? ` (${status})` : ''}
      </h3>
      <p className="mt-2 text-sm text-ink-700">{message}</p>
    </div>
  );
}
