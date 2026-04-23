export default function Spinner() {
  return (
    <div className="flex items-center justify-center py-20" data-testid="spinner">
      <div className="h-12 w-12 animate-spin rounded-full border-4 border-ink-900/10 border-t-accent-500" />
    </div>
  );
}
