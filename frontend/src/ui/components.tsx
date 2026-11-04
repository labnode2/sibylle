// The Gazette's base components (canvas G-Style). Layout-specific pieces live with their feature.
import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type AnchorHTMLAttributes,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from 'react';
import { useTranslation } from 'react-i18next';
import { Link, NavLink, type LinkProps } from 'react-router';

import coinUrl from './assets/coin.png';
import laurelGreenUrl from './assets/laurel-green.png';
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

/** The newspaper's title: on la une and the public pages only (canvas B-Accueil, G-Rejoindre). */
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

/** The title in one line, back to la une: the computer's other pages (canvas B-Web-Prono). */
export function Logo({ to }: { to: string }) {
  const { t } = useTranslation();
  return (
    <Link to={to} className={styles.logo}>
      <CrystalBall size={48} label={t('masthead.ball')} />
      <span className={styles.logoName}>{t('masthead.name')}</span>
    </Link>
  );
}

/** A page's top line on a phone: the way back, and on the right what the page is
 *  (« ‹ LA UNE · PRONO N° 128 »). On a computer the right side can stay on phones only. */
export function TopBar({
  back,
  backLabel,
  aside,
  asideOnPhoneOnly = false,
}: {
  back: LinkProps['to'];
  backLabel: string;
  aside?: ReactNode;
  asideOnPhoneOnly?: boolean;
}) {
  return (
    <div className={styles.topBar}>
      <Link to={back} className={styles.back}>
        <Icon name="chevronLeft" size={24} />
        <span>{backLabel}</span>
      </Link>
      {aside && (
        <span className={cx(styles.topBarAside, asideOnPhoneOnly && 'only-mobile')}>{aside}</span>
      )}
    </div>
  );
}

/** An intertitle in Bricolage with, on its right, a word in mono (« Le classement · NOVEMBRE »). */
export function SectionHead({
  title,
  meta,
  id,
  level = 2,
}: {
  title: ReactNode;
  meta?: ReactNode;
  id?: string;
  level?: 1 | 2;
}) {
  const Heading = level === 1 ? 'h1' : 'h2';
  return (
    <div className={styles.sectionHead}>
      <Heading id={id} className={styles.intertitle}>
        {title}
      </Heading>
      {meta !== undefined && <span className={styles.sectionMeta}>{meta}</span>}
    </div>
  );
}

/** The question with its key idea underlined in gold, once per screen: what follows the colon
 *  (« Derby de la Côte d'Azur : <u>Nice ou Monaco ?</u> »). Without a colon, nothing is. */
export function KeyPhrase({ text }: { text: string }) {
  const match = /^(.*?\S)(\s*:\s+)(\S.*)$/su.exec(text);
  if (!match) return <>{text}</>;
  return (
    <>
      {match[1]}
      {match[2]}
      <mark className="key-phrase">{match[3]}</mark>
    </>
  );
}

export type SegmentOption<T extends string> = { value: T; label: ReactNode };

/** Joined choices in a 2 px frame, the chosen one in ink (canvas G-Créer « TYPE »,
 *  G-Classement « LAURIERS / PRONOS GAGNÉS »). `tabs` draws them as underlined words. */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  variant = 'boxes',
  mode = 'pressed',
}: {
  label: string;
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  variant?: 'boxes' | 'tabs';
  mode?: 'pressed' | 'radio';
}) {
  return (
    <div
      className={variant === 'tabs' ? styles.tabs : styles.segmented}
      role={mode === 'radio' ? 'radiogroup' : 'group'}
      aria-label={label}
      style={{ ['--segments' as string]: options.length }}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role={mode === 'radio' ? 'radio' : undefined}
          aria-checked={mode === 'radio' ? value === option.value : undefined}
          aria-pressed={mode === 'pressed' ? value === option.value : undefined}
          className={variant === 'tabs' ? styles.tabsButton : styles.segment}
          onClick={() => onChange(option.value)}
        >
          <span>{option.label}</span>
        </button>
      ))}
    </div>
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
  block = false,
}: {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  label: string;
  format?: (value: number) => string;
  /** Takes the whole width of its column. */
  block?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div
      className={cx(styles.stepper, block && styles.stepperBlock)}
      role="group"
      aria-label={label}
    >
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

/** Laurels: green for what is staked, won and scored (the balance, a stake, a gain, a pot, a
 *  ranking); gold only for the gold total, the balance plus the stakes in play, that Monday
 *  turns into coins. `label` names the amount for screen readers. */
export function Laurel({
  value,
  size = 16,
  tone = 'green',
  label,
}: {
  value?: number;
  size?: 16 | 32;
  tone?: 'gold' | 'green';
  label?: string;
}) {
  const { t } = useTranslation();
  return (
    <span className={styles.laurel}>
      {value !== undefined && <span>{value}</span>}
      <img
        src={tone === 'green' ? laurelGreenUrl : laurelUrl}
        width={size}
        height={size}
        alt=""
        className="pixelated"
      />
      <span className="visually-hidden">
        {label ?? (value === undefined ? t('laurelsWord') : t('laurels', { count: value }))}
      </span>
    </span>
  );
}

/** Coins: what Monday's conversion of gold laurels brings, spent in the collection. */
export function Coins({ value, size = 16 }: { value?: number; size?: 16 | 32 }) {
  const { t } = useTranslation();
  return (
    <span className={styles.laurel}>
      {value !== undefined && <span>{value}</span>}
      <img src={coinUrl} width={size} height={size} alt="" className="pixelated" />
      <span className="visually-hidden">
        {value === undefined ? t('coinsWord') : t('coins', { count: value })}
      </span>
    </span>
  );
}

/** A word of explanation beside its trigger: on hover, on focus, or pinned by a tap. It stays
 *  while the pointer is over it and Escape closes it (WCAG 1.4.13). */
export function Tip({
  children,
  tip,
  label,
  align = 'end',
}: {
  children: ReactNode;
  tip: ReactNode;
  /** The trigger's name when its content does not say it (a « ? »). */
  label?: string;
  /** Which edge of the trigger the bubble lines up with. */
  align?: 'start' | 'end';
}) {
  const id = useId();
  const bubble = useRef<HTMLSpanElement>(null);
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const open = hovered || pinned;
  // The bubble stays on the screen: shifted back inside when it would cross an edge.
  useLayoutEffect(() => {
    const element = bubble.current;
    if (!open || !element) return;
    element.style.transform = '';
    const box = element.getBoundingClientRect();
    const margin = 8;
    const shift =
      box.left < margin
        ? margin - box.left
        : box.right > window.innerWidth - margin
          ? window.innerWidth - margin - box.right
          : 0;
    element.style.transform = shift ? `translateX(${Math.round(shift)}px)` : '';
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setHovered(false);
        setPinned(false);
      }
    };
    document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [open]);
  return (
    <span
      className={styles.tip}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        type="button"
        className={styles.tipTrigger}
        aria-label={label}
        aria-describedby={id}
        aria-expanded={open}
        onFocus={() => setHovered(true)}
        onBlur={() => {
          setHovered(false);
          setPinned(false);
        }}
        onClick={() => setPinned((value) => !value)}
      >
        {children}
      </button>
      <span
        ref={bubble}
        role="tooltip"
        id={id}
        className={cx(styles.tipBubble, align === 'start' && styles.tipStart)}
        hidden={!open}
      >
        {tip}
      </span>
    </span>
  );
}

/** A member's three counters: green laurels to stake, gold laurels in all, coins to spend.
 *  Each one explains itself on hover, focus or tap; `captions` also writes what each one is. */
export function Wallet({
  balance,
  gold,
  coins,
  captions = false,
}: {
  balance: number;
  gold: number;
  coins: number;
  captions?: boolean;
}) {
  const { t } = useTranslation();
  const counters = [
    {
      key: 'green',
      node: <Laurel value={balance} label={t('wallet.greenLabel', { count: balance })} />,
    },
    {
      key: 'gold',
      node: <Laurel value={gold} tone="gold" label={t('wallet.goldLabel', { count: gold })} />,
    },
    { key: 'coins', node: <Coins value={coins} /> },
  ];
  return (
    <span className={cx(styles.wallet, captions && styles.walletCaptions)}>
      {counters.map(({ key, node }) => (
        <Tip key={key} tip={t(`wallet.${key}Hint`)}>
          <span className={styles.counter}>
            {node}
            {captions && (
              <span className={styles.caption} aria-hidden="true">
                {t(`wallet.${key}`)}
              </span>
            )}
          </span>
        </Tip>
      ))}
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

/** A whole line that switches, its words on the left (canvas G-Créer « Relancer si… »). */
export function SwitchRow({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  hint?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={styles.switchRow}
      onClick={() => onChange(!checked)}
    >
      <span className={styles.switchRowText}>
        <span className={styles.switchRowLabel}>{label}</span>
        {hint && <span className={styles.switchRowHint}>{hint}</span>}
      </span>
      <span className={styles.switch} aria-hidden="true">
        <span className={styles.switchKnob} />
      </span>
    </button>
  );
}

export { styles as uiStyles };
