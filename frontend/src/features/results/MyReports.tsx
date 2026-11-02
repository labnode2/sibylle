// What became of the member's own reports on a prono: waiting, settled or dismissed, with the
// editor's note.
import { useTranslation } from 'react-i18next';

import type { components } from '../../api/schema';
import styles from './results.module.css';

type Report = components['schemas']['ReportOut'];

export function MyReports({ reports }: { reports: Report[] }) {
  const { t } = useTranslation('results');
  if (reports.length === 0) return null;
  return (
    <section className={styles.myReports} aria-label={t('myReports.title')}>
      <span className={styles.label}>{t('myReports.title')}</span>
      <ul>
        {reports.map((report) => (
          <li key={report.id}>
            <span>
              {t(`report.${report.kind}`)} : {t(`myReports.${report.state}`)}
            </span>
            {report.resolution_note && <q>{report.resolution_note}</q>}
          </li>
        ))}
      </ul>
    </section>
  );
}
