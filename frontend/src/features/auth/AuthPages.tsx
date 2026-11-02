// Sign-in, sign-up, forgotten password, new password and address check (Gazette style).
import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router';

import { Button, Field, Kicker } from '../../ui/components';
import { useFormErrors } from '../forms';
import { useConfirmReset, useLogin, useRequestReset, useSignup, useVerifyEmail } from './api';
import styles from './auth.module.css';
import { nextPath } from './RequireAuth';

function Alert({ children }: { children?: string }) {
  if (!children) return null;
  return (
    <p className={styles.alert} role="alert">
      {children}
    </p>
  );
}

export function LoginPage() {
  const { t } = useTranslation('auth');
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const login = useLogin();
  const errors = useFormErrors(login.error);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate({ email, password }, { onSuccess: () => navigate(nextPath(search)) });
  };

  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('login.title')}</h1>
      <form className={styles.form} onSubmit={submit} noValidate>
        <Alert>{errors.message}</Alert>
        <Field
          label={t('fields.email')}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Field
          label={t('fields.password')}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Button type="submit" block disabled={login.isPending}>
          {t('login.submit')}
        </Button>
      </form>
      <div className={styles.links}>
        <Link to={`/inscription?${search.toString()}`}>{t('login.signup')}</Link>
        <Link to="/mot-de-passe/oubli">{t('login.forgot')}</Link>
      </div>
    </section>
  );
}

export function SignupPage() {
  const { t } = useTranslation('auth');
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const signup = useSignup();
  const errors = useFormErrors(signup.error);
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '' });
  const set = (name: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm({ ...form, [name]: e.target.value });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    signup.mutate(form, { onSuccess: () => navigate(nextPath(search)) });
  };

  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('signup.title')}</h1>
      <p className={styles.lead}>{t('signup.lead')}</p>
      <form className={styles.form} onSubmit={submit} noValidate>
        <Alert>{errors.message}</Alert>
        <div className={styles.row}>
          <Field
            label={t('fields.firstName')}
            autoComplete="given-name"
            value={form.first_name}
            onChange={set('first_name')}
            error={errors.field('first_name')}
            required
          />
          <Field
            label={t('fields.lastName')}
            autoComplete="family-name"
            value={form.last_name}
            onChange={set('last_name')}
            error={errors.field('last_name')}
            required
          />
        </div>
        <span className={styles.note}>{t('signup.private')}</span>
        <Field
          label={t('fields.email')}
          type="email"
          autoComplete="email"
          value={form.email}
          onChange={set('email')}
          error={errors.field('email')}
          required
        />
        <Field
          label={t('fields.password')}
          type="password"
          autoComplete="new-password"
          hint={t('signup.passwordHint')}
          value={form.password}
          onChange={set('password')}
          error={errors.field('password')}
          required
        />
        <Button type="submit" block disabled={signup.isPending}>
          {t('signup.submit')}
        </Button>
      </form>
      <div className={styles.links}>
        <Link to={`/connexion?${search.toString()}`}>{t('signup.login')}</Link>
      </div>
    </section>
  );
}

export function ForgotPasswordPage() {
  const { t } = useTranslation('auth');
  const request = useRequestReset();
  const errors = useFormErrors(request.error);
  const [email, setEmail] = useState('');

  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('forgot.title')}</h1>
      {request.isSuccess ? (
        <p role="status">{t('forgot.sent')}</p>
      ) : (
        <form
          className={styles.form}
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            request.mutate(email);
          }}
        >
          <p className={styles.lead}>{t('forgot.lead')}</p>
          <Alert>{errors.message}</Alert>
          <Field
            label={t('fields.email')}
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Button type="submit" block disabled={request.isPending}>
            {t('forgot.submit')}
          </Button>
        </form>
      )}
      <Link to="/connexion">{t('backToLogin')}</Link>
    </section>
  );
}

export function ResetPasswordPage() {
  const { t } = useTranslation('auth');
  const [search] = useSearchParams();
  const confirm = useConfirmReset();
  const errors = useFormErrors(confirm.error);
  const [password, setPassword] = useState('');
  const token = search.get('jeton') ?? '';

  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('reset.title')}</h1>
      {confirm.isSuccess ? (
        <p role="status">{t('reset.done')}</p>
      ) : (
        <form
          className={styles.form}
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            confirm.mutate({ token, password });
          }}
        >
          <Alert>{errors.message}</Alert>
          <Field
            label={t('fields.newPassword')}
            type="password"
            autoComplete="new-password"
            hint={t('signup.passwordHint')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.field('password')}
            required
          />
          <Button type="submit" block disabled={confirm.isPending || !token}>
            {t('reset.submit')}
          </Button>
        </form>
      )}
      <Link to="/connexion">{t('backToLogin')}</Link>
    </section>
  );
}

export function VerifyEmailPage() {
  const { t } = useTranslation('auth');
  const [search] = useSearchParams();
  const verify = useVerifyEmail();
  const token = search.get('jeton');
  const { mutate } = verify;

  useEffect(() => {
    if (token) mutate(token);
  }, [token, mutate]);

  return (
    <section className={styles.page}>
      <Kicker tone="indigo">{t('verify.kicker')}</Kicker>
      <h1 className={styles.title}>
        {verify.isSuccess
          ? t('verify.done')
          : verify.isError || !token
            ? t('verify.failed')
            : t('verify.pending')}
      </h1>
      <Link to="/">{t('verify.continue')}</Link>
    </section>
  );
}
