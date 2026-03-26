interface Props {
  message: string;
  status?: number;
}

export default function ErrorMessage({ message, status }: Props) {
  return (
    <div className="mx-auto mt-8 max-w-lg rounded-lg border border-red-500/20 bg-red-500/10 p-4">
      <h3 className="font-semibold text-red-400">
        Ошибка{status ? ` (${status})` : ''}
      </h3>
      <p className="mt-1 text-sm text-red-300">{message}</p>
    </div>
  );
}
