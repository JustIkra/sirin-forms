import { getExportUrl } from '../api/forecast';

interface Props {
  date: string;
  method: string;
  type: string;
}

const FORMATS = [
  { label: 'CSV', format: 'csv' },
  { label: 'JSON', format: 'json' },
  { label: 'XLSX', format: 'xlsx' },
] as const;

export default function ExportButtons({ date, method, type }: Props) {
  return (
    <span className="inline-flex gap-1">
      {FORMATS.map(({ label, format }) => (
        <a
          key={format}
          href={getExportUrl(date, method, type, format)}
          download
          className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 transition-colors hover:bg-slate-50"
        >
          {label}
        </a>
      ))}
    </span>
  );
}
