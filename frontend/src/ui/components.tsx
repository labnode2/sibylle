// The Gazette's base components (canvas G-Style). Layout-specific pieces live with their feature.
import {
  useId,
  type AnchorHTMLAttributes,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from 'react';
import { useTranslation } from 'react-i18next';
import { Link, NavLink, type LinkProps } from 'react-router';

import laurelUrl from './assets/laurel.png';
import { CrystalBall } from './CrystalBall';
import { ICONS, type IconName } from './icons';
import styles from './ui.module.css';

const cx = (...names: (string | false | null | undefined)[]) => names.filter(Boolean).join(' ');

export function Icon({ name, size = 12 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 12 12"
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      <path fill="currentColor" d={ICONS[name]} />
    </svg>
  );
}

export function Rule({ variant = 'thin' }: { variant?: 'double' | 'thin' | 'light' }) {
  const className = {
    double: styles.ruleDouble,
    thin: styles.ruleThin,
    light: styles.ruleLight,
  }[variant];
  return <div aria-hidden="true" className={className} />;
}

export function Masthead({ size = 'compact' }: { size?: 'compact' | 'large' }) {
  const { t } = useTranslation();
  return (
    <>
      <header className={cx(styles.masthead, size === 'large' && styles.mastheadLarge)}>
        <CrystalBall size={size === 'large' ? 64 : 48} label={t('masthead.ball')} />
        <div className={styles.mastheadTitle}>
          <span className={styles.mastheadKicker}>{t('masthead.kicker')}</span>
          <span className={styles.mastheadName}>{t('masthead.name')}</span>
        </div>
      </header>
      <Rule variant="double" />
    </>
  );
}

export function Card({
  children,
  shadow = 4,
  className,
  as: Tag = 'section',
  ...rest
}: {
  children: ReactNode;
  shadow?: 0 | 4 | 6;
  className?: string;
  as?: 'section' | 'div' | 'article' | 'aside';
} & Record<`aria-${string}`, string | undefined>) {
  return (
    <Tag
      className={cx(
        styles.card,
        shadow === 6 && styles.cardLarge,
        shadow === 0 && styles.cardFlat,
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}

type ButtonVariant = 'primary' | 'secondary' | 'link';

const buttonClass = (variant: ButtonVariant, block?: boolean, className?: string) =>
  cx(
    styles.button,
    variant === 'secondary' && styles.buttonSecondary,
    variant === 'link' && styles.buttonLink,
    block && styles.buttonBlock,
    className,
  );

export function Button({
  variant = 'primary',
  block,
  className,
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; block?: boolean }) {
  return <button type={type} className={buttonClass(variant, block, className)} {...props} />;
}

export function ButtonLink({
  variant = 'primary',
  block,
  className,
  ...props
}: LinkProps & { variant?: ButtonVariant; block?: boolean }) {
  return <Link className={buttonClass(variant, block, className)} {...props} />;
}

export function ExternalLink(props: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a target="_blank" rel="noreferrer noopener" {...props} />;
}

export function Field({
  label,
  hint,
  error,
  ...input
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string }) {
  const id = useId();
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ');
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.fieldLabel}>
        {label}
      </label>
      <input
        id={id}
        className={styles.fieldInput}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        {...input}
      />
      {hint && (
        <span id={`${id}-hint`} className={styles.fieldHint}>
          {hint}
        </span>
      )}
      {error && (
        <span id={`${id}-error`} role="alert" className={styles.fieldError}>
          {error}
        </span>
      )}
    </div>
  );
}

export function Kicker({
  children,
  tone = 'muted',
}: {
  children: ReactNode;
  tone?: 'muted' | 'indigo';
}) {
  return (
    <span className={cx(styles.kicker, tone === 'indigo' && styles.kickerIndigo)}>{children}</span>
  );
}

export function Chip({
  children,
  variant = 'outline',
}: {
  children: ReactNode;
  variant?: 'outline' | 'ink' | 'grey' | 'stamp';
}) {
  return (
    <span
      className={cx(
        styles.chip,
        variant === 'ink' && styles.chipInk,
        variant === 'grey' && styles.chipGrey,
        variant === 'stamp' && styles.chipStamp,
      )}
    >
      {children}
    </span>
  );
}

export function Stepper({
  value,
  onChange,
  min,
  max,
  step = 1,
  label,
  format = String,
}: {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  label: string;
  format?: (value: number) => string;
}) {
  const { t } = useTranslation();
  return (
    <div className={styles.stepper} role="group" aria-label={label}>
      <button
        type="button"
        className={styles.stepperButton}
        onClick={() => onChange(Math.max(min, value - step))}
        disabled={value <= min}
        aria-label={t('stepper.less')}
      >
        <Icon name="minus" size={12} />
      </button>
      <output className={styles.stepperValue} aria-live="polite">
        {format(value)}
      </output>
      <button
        type="button"
        className={styles.stepperButton}
        onClick={() => onChange(Math.min(max, value + step))}
        disabled={value >= max}
        aria-label={t('stepper.more')}
      >
        <Icon name="plus" size={12} />
      </button>
    </div>
  );
}

export type Tab = { to: string; label: string; icon: IconName; end?: boolean };

export function TabBar({ tabs, label }: { tabs: Tab[]; label: string }) {
  return (
    <nav className={styles.tabbar} aria-label={label} style={{ ['--tabs' as string]: tabs.length }}>
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) => cx(styles.tab, isActive && styles.tabActive)}
        >
          <Icon name={tab.icon} size={24} />
          <span className={styles.tabLabel}>{tab.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function Laurel({ value, size = 16 }: { value?: number; size?: 16 | 32 }) {
  const { t } = useTranslation();
  return (
    <span className={styles.laurel}>
      {value !== undefined && <span>{value}</span>}
      <img src={laurelUrl} width={size} height={size} alt="" className="pixelated" />
      <span className="visually-hidden">
        {value === undefined ? t('laurelsWord') : t('laurels', { count: value })}
      </span>
    </span>
  );
}

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={styles.switch}
      onClick={() => onChange(!checked)}
    >
      <span className={styles.switchKnob} />
    </button>
  );
}

export { styles as uiStyles };
