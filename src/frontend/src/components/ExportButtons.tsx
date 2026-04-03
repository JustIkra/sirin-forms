import { useState } from 'react';
import { getExportUrl } from '../api/forecast';

interface Props {
  date: string;
  method: string;
  type: string;
}

const FORMATS = [
  { label: 'PDF', format: 'pdf' },
  { label: 'CSV', format: 'csv' },
  { label: 'XLSX', format: 'xlsx' },
  { label: 'JSON', format: 'json' },
] as const;

export default function ExportButtons({ date, method, type }: Props) {
  const [downloading, setDownloading] = useState<string | null>(null);

  const handlePdfDownload = async () => {
    const element = document.getElementById(`print-area-${type}`);
    if (!element) return;

    setDownloading('pdf');
    try {
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import('html2canvas-pro'),
        import('jspdf'),
      ]);

      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        backgroundColor: '#0f172a',
        ignoreElements: (el: Element) => el.classList.contains('no-print'),
      });

      const imgData = canvas.toDataURL('image/jpeg', 0.98);
      const pdf = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' });
      const pageW = pdf.internal.pageSize.getWidth() - 20;
      const pageH = pdf.internal.pageSize.getHeight() - 20;
      const imgH = (canvas.height * pageW) / canvas.width;

      let offset = 0;
      while (offset < imgH) {
        if (offset > 0) pdf.addPage();
        pdf.addImage(imgData, 'JPEG', 10, 10 - offset, pageW, imgH);
        offset += pageH;
      }

      pdf.save(`${type}_${date}_${method}.pdf`);
    } catch (err) {
      console.error('PDF generation failed:', err);
      alert('Не удалось сформировать PDF');
    } finally {
      setDownloading(null);
    }
  };

  const handleDownload = async (format: string) => {
    if (format === 'pdf') {
      return handlePdfDownload();
    }

    setDownloading(format);
    try {
      const url = getExportUrl(date, method, type, format);
      const res = await fetch(url);
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: 'Ошибка скачивания' }));
        alert(body.detail ?? 'Ошибка скачивания');
        return;
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      const disposition = res.headers.get('Content-Disposition');
      const filenameMatch = disposition?.match(/filename="?([^"]+)"?/);
      a.download = filenameMatch?.[1] ?? `${type}_${date}_${method}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objectUrl);
    } catch {
      alert('Не удалось скачать файл');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <span className="inline-flex gap-1 no-print">
      {FORMATS.map(({ label, format }) => (
        <button
          key={format}
          onClick={() => handleDownload(format)}
          disabled={downloading === format}
          className="rounded border border-white/10 px-2 py-1 text-xs text-slate-400 transition-colors hover:bg-white/[0.06] hover:text-white disabled:opacity-50"
        >
          {downloading === format ? '...' : label}
        </button>
      ))}
    </span>
  );
}
