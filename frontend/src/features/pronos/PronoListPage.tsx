// The newsroom's pronos, by state and section. New pronos and bets refresh the list live.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { formatDate, formatNumber } from '../../i18n';
import { Button, ButtonLink, Card, Icon, Laurel } from '../../ui/components';
import { useOrg } from '../orgs/api';
import { usePronoList, useSections, type PronoSummary } from './api';
import styles from './pronos.module.css';

const FILTERS = {
  open: ['scheduled', 'open'],
  closed: ['closed'],
  resolved: ['resolved', 'cancelled'],
} as const;

type Filter = keyof typeof FILTERS;

const shortDate = (value: string) =>
  formatDate(value, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).toUpperCase();

function PronoItem({ orgId, prono }: { orgId: string; prono: PronoSummary }) {
  const { t } = useTranslation('pronos');
  const when =
    prono.state === 'scheduled' && prono.opens_at
      ? t('list.opensAt', { date: shortDate(prono.opens_at) })
      : prono.closes_at
        ? t(prono.state === 'open' ? 'list.closesAt' : 'list.closedAt', {
            date: shortDate(prono.closes_at),
          })
        : null;
  return (
    <li>
      <Card as="article">
        <Link to={`/o/${orgId}/pronos/${prono.id}`} className={styles.item}>
          <span className={styles.kicker}>
            {prono.section.name.toUpperCase()} · {t(`state.${prono.state}`)}
          </span>
          <span className={styles.itemTitle}>{prono.question}</span>
          <span className={styles.meta}>
            {[
              when,
              t('list.bets', { count: prono.bet_count }),
              prono.message_count > 0 && t('list.messages', { count: prono.message_count }),
            ]
              .filter(Boolean)
              .join(' · ')}
          </span>
          <span className={styles.meta}>
            {t('list.pot', { pot: formatNumber(prono.pot) })} <Laurel />
          </span>
        </Link>
      </Card>
    </li>
  );
}

export function PronoListPage() {
  const { t } = useTranslation('pronos');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const sections = useSections(orgId);
  const [filter, setFilter] = useState<Filter>('open');
  const [section, setSection] = useState('');
  const list = usePronoList(orgId, [...FILTERS[filter]], section || undefined);
  const items = list.data?.pages.flatMap((page) => page.items) ?? [];
  const proposing = org.data?.my_membership.role === 'reader';

  return (
    <div className={styles.page}>
      <div className={styles.top}>
        <h1 className={styles.question}>{t('list.title')}</h1>
        {org.data && (
          <ButtonLink to={`/o/${orgId}/pronos/nouveau`} variant="secondary">
            <Icon name="plus" size={12} /> {t(proposing ? 'list.propose' : 'list.new')}
          </ButtonLink>
        )}
      </div>
      <div className={styles.filters} role="group" aria-label={t('list.filters')}>
        {(Object.keys(FILTERS) as Filter[]).map((value) => (
          <button
            key={value}
            type="button"
            className={styles.filter}
            aria-pressed={filter === value}
            onClick={() => setFilter(value)}
          >
            {t(`list.${value}`)}
          </button>
        ))}
        {sections.data && sections.data.length > 1 && (
          <select
            className={styles.select}
            aria-label={t('list.section')}
            value={section}
            onChange={(event) => setSection(event.target.value)}
          >
            <option value="">{t('list.allSections')}</option>
            {sections.data.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        )}
      </div>
      {list.isPending ? (
        <p role="status">{t('common:shell.loading')}</p>
      ) : items.length === 0 ? (
        <p className={styles.empty}>{t('list.empty')}</p>
      ) : (
        <ul className={styles.list}>
          {items.map((prono) => (
            <PronoItem key={prono.id} orgId={orgId} prono={prono} />
          ))}
        </ul>
      )}
      {list.hasNextPage && (
        <Button
          variant="secondary"
          onClick={() => void list.fetchNextPage()}
          disabled={list.isFetchingNextPage}
        >
          {t('list.more')}
        </Button>
      )}
    </div>
  );
}
