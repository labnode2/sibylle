// Open reports: the prono, who reported it and why; the editor closes each one as resolved
// (after correcting the result on the prono, say) or dismissed, with a note its author reads.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { formatDate } from '../../i18n';
import { Button, Card, Kicker } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { useHandleReport, useReports, type ReportDetail } from './api';
import styles from './admin.module.css';

function ReportCard({ orgId, report }: { orgId: string; report: ReportDetail }) {
  const { t } = useTranslation('admin');
  const handle = useHandleReport(orgId);
  const [note, setNote] = useState('');
  const close = (state: 'resolved' | 'dismissed') =>
    handle.mutate({ reportId: report.id, state, note });

  return (
    <Card className={styles.panel} aria-label={report.prono.question}>
      <Kicker tone="indigo">
        {t(`reports.kind.${report.kind}`)} ·{' '}
        {formatDate(report.created_at, {
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit',
        }).toUpperCase()}
      </Kicker>
      <Link to={`/o/${orgId}/pronos/${report.prono.id}`} className={styles.rowName}>
        {report.prono.question}
      </Link>
      <div className={styles.memberHead}>
        <PixelImage image={report.reporter.avatar} size={24} />
        <span>{t('reports.by', { pseudo: report.reporter.pseudo })}</span>
      </div>
      {report.message && <blockquote className={styles.quote}>{report.message}</blockquote>}
      {report.kind === 'result_error' && <p className={styles.hint}>{t('reports.correctHint')}</p>}
      <label className={styles.block}>
        <span className={styles.label}>{t('reports.note')}</span>
        <textarea
          className={styles.textarea}
          maxLength={500}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      <div className={styles.actions}>
        <Button variant="secondary" onClick={() => close('dismissed')} disabled={handle.isPending}>
          {t('reports.dismiss')}
        </Button>
        <Button onClick={() => close('resolved')} disabled={handle.isPending}>
          {t('reports.resolve')}
        </Button>
      </div>
    </Card>
  );
}

export function ReportsPage() {
  const { t } = useTranslation('admin');
  const { orgId = '' } = useParams();
  const reports = useReports(orgId);
  if (!reports.data) return <p role="status">{t('common:shell.loading')}</p>;
  if (reports.data.length === 0) return <p className={styles.hint}>{t('reports.none')}</p>;
  return (
    <>
      {reports.data.map((report) => (
        <ReportCard key={report.id} orgId={orgId} report={report} />
      ))}
    </>
  );
}
