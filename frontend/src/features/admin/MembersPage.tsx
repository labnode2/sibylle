// The editor's members page: each member's green laurels and role, laurel adjustments with a
// reason (and the laurels they leave), removal; the invitations under way and the newsroom's
// access code.
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import type { MemberListed } from '../../api/types';
import { formatDate } from '../../i18n';
import { Button, Chip, Field, Kicker, Laurel } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { toast } from '../../ui/Toaster';
import { useOrg } from '../orgs/api';
import {
  useAccessCode,
  useInvitations,
  useMemberActions,
  useMembers,
  useRevokeInvitation,
  type Invitation,
  type Role,
} from './api';
import { InvitePanel } from './InvitePanel';
import styles from './admin.module.css';

const ROLES: Role[] = ['reader', 'journalist', 'editor'];

function MemberRow({
  orgId,
  member,
  isMe,
}: {
  orgId: string;
  member: MemberListed;
  isMe: boolean;
}) {
  const { t } = useTranslation('admin');
  const { changeRole, remove, adjust } = useMemberActions(orgId);
  const [adjusting, setAdjusting] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');

  // A whole number of laurels, other than 0: what the adjustment would leave.
  const value = Number(amount);
  const valid = amount.trim() !== '' && Number.isInteger(value) && value !== 0;

  const submitAdjustment = (event: FormEvent) => {
    event.preventDefault();
    adjust.mutate(
      { memberId: member.id, amount: value, reason: reason.trim() },
      {
        onSuccess: () => {
          toast.success(t('members.adjusted', { amount: value > 0 ? `+${value}` : value }));
          setAdjusting(false);
          setAmount('');
          setReason('');
        },
      },
    );
  };

  return (
    <li className={styles.member}>
      <div className={styles.memberHead}>
        <PixelImage image={member.avatar} size={32} />
        <span className={styles.rowName}>
          {member.pseudo}
          {isMe && <span className={styles.you}> {t('members.you')}</span>}
        </span>
        <Laurel
          value={member.balance}
          label={t('common:wallet.greenLabel', { count: member.balance })}
        />
        <label className={`${styles.select} ${styles[`role_${member.role}`]}`}>
          <span className="visually-hidden">{t('members.role', { pseudo: member.pseudo })}</span>
          <select
            value={member.role}
            disabled={changeRole.isPending}
            onChange={(event) => {
              const role = event.target.value as Role;
              changeRole.mutate(
                { memberId: member.id, role },
                {
                  onSuccess: () =>
                    toast.success(
                      t('members.roleChanged', { pseudo: member.pseudo, role: t(`roles.${role}`) }),
                    ),
                },
              );
            }}
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {t(`roles.${role}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className={styles.inline}>
        <Button variant="link" onClick={() => setAdjusting((open) => !open)}>
          {t('members.adjust')}
        </Button>
        {!isMe &&
          (removing ? (
            <>
              <span>{t('members.removeConfirm', { pseudo: member.pseudo })}</span>
              <Button variant="secondary" onClick={() => setRemoving(false)}>
                {t('members.keep')}
              </Button>
              <Button
                onClick={() =>
                  remove.mutate(member.id, {
                    onSuccess: () => toast.success(t('members.removed', { pseudo: member.pseudo })),
                  })
                }
                disabled={remove.isPending}
              >
                {t('members.removeYes')}
              </Button>
            </>
          ) : (
            <Button variant="link" onClick={() => setRemoving(true)}>
              {t('members.remove')}
            </Button>
          ))}
      </div>
      {adjusting && (
        <form className={styles.adjust} onSubmit={submitAdjustment} noValidate>
          <Field
            label={t('members.amount')}
            hint={t('members.amountHint')}
            type="number"
            inputMode="numeric"
            step={1}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
          <p className={styles.after} aria-live="polite">
            {t('members.balance', { count: member.balance })}
            {valid && ` · ${t('members.after', { count: member.balance + value })}`}
          </p>
          <Field
            label={t('members.reason')}
            value={reason}
            maxLength={200}
            onChange={(event) => setReason(event.target.value)}
          />
          <Button type="submit" disabled={adjust.isPending || !valid || !reason.trim()}>
            {t('members.adjustSubmit', { pseudo: member.pseudo })}
          </Button>
        </form>
      )}
    </li>
  );
}

function invitationState(invitation: Invitation): 'revoked' | 'expired' | 'full' | 'active' {
  if (invitation.revoked_at) return 'revoked';
  if (new Date(invitation.expires_at) <= new Date()) return 'expired';
  if (invitation.places_left === 0) return 'full';
  return 'active';
}

function Invitations({ orgId }: { orgId: string }) {
  const { t } = useTranslation('admin');
  const invitations = useInvitations(orgId);
  const revoke = useRevokeInvitation(orgId);
  const list = invitations.data ?? [];
  if (list.length === 0) return null;
  return (
    <section className={styles.panel} aria-label={t('invitations.title')}>
      <h2 className={styles.heading}>{t('invitations.title')}</h2>
      <ul className={styles.rows}>
        {list.map((invitation) => {
          const state = invitationState(invitation);
          return (
            <li key={invitation.id} className={styles.row}>
              <span className={styles.rowName}>
                {invitation.kind === 'email' ? invitation.email : t('invitations.link')}
                <span className={styles.hint}>
                  {t(`invitations.roles.${invitation.role}`)} ·{' '}
                  {t('invitations.uses', {
                    used: invitation.use_count,
                    max: invitation.max_uses,
                  })}{' '}
                  ·{' '}
                  {t('invitations.until', {
                    date: formatDate(invitation.expires_at, { day: 'numeric', month: 'long' }),
                  })}
                </span>
              </span>
              {state === 'active' ? (
                <Button
                  variant="link"
                  onClick={() => revoke.mutate(invitation.id)}
                  disabled={revoke.isPending}
                >
                  {t('invitations.revoke')}
                </Button>
              ) : (
                <Chip variant="grey">{t(`invitations.${state}`)}</Chip>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function AccessCode({ orgId, code }: { orgId: string; code: string | null }) {
  const { t } = useTranslation('admin');
  const { renew, disable } = useAccessCode(orgId);
  return (
    <section className={styles.panel} aria-label={t('code.title')}>
      <h2 className={styles.heading}>{t('code.title')}</h2>
      <p className={styles.hint}>{t('code.hint')}</p>
      <div className={styles.inline}>
        {code ? <Chip variant="grey">{code}</Chip> : <span>{t('code.none')}</span>}
        <Button variant="secondary" onClick={() => renew.mutate()} disabled={renew.isPending}>
          {t(code ? 'code.renew' : 'code.create')}
        </Button>
        {code && (
          <Button variant="link" onClick={() => disable.mutate()} disabled={disable.isPending}>
            {t('code.disable')}
          </Button>
        )}
      </div>
    </section>
  );
}

export function MembersPage() {
  const { t } = useTranslation('admin');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const members = useMembers(orgId);
  if (!org.data) return null;
  const me = org.data.my_membership;

  return (
    <>
      <section className={styles.panel} aria-label={t('members.title')}>
        <h2 className={styles.heading}>{t('members.title')}</h2>
        <Kicker>{t('members.count', { count: members.data?.length ?? 0 })}</Kicker>
        <ul className={styles.rows}>
          {(members.data ?? []).map((member) => (
            <MemberRow key={member.id} orgId={orgId} member={member} isMe={member.id === me.id} />
          ))}
        </ul>
      </section>
      <InvitePanel orgId={orgId} accessCode={null} />
      <Invitations orgId={orgId} />
      <AccessCode orgId={orgId} code={org.data.access_code} />
    </>
  );
}
