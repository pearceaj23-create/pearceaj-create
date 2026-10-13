import Link from "next/link";
import { signIn, signUp } from "./actions";

const errors = {
  invalid_input: "Enter an email and password to continue.",
  sign_in_failed: "We couldn't sign you in. Check your details and try again.",
  sign_up_failed: "We couldn't create your account. Try again or contact the project owner.",
  password_too_short: "Choose a password with at least 8 characters.",
  configuration: "The app needs its site URL configured before sign-up can continue.",
  auth_callback: "That sign-in link could not be verified. Please try again.",
};

export default async function LoginPage({ searchParams }) {
  const params = await searchParams;
  const error = errors[params?.error];
  const message = params?.message === "check_email"
    ? "Check your email for a confirmation link, then come back here to sign in."
    : null;
  const next = typeof params?.next === "string" ? params.next : "/assistant";

  return (
    <main className="public-shell">
      <header className="public-topbar">
        <Link className="public-brand" href="/"><span className="brand-mark">✦</span> ASTER</Link>
        <Link className="public-nav" href="/">Back home</Link>
      </header>
      <section className="auth-wrap">
        <div className="auth-card">
          <p className="page-eyebrow">Your own private space</p>
          <h1>Welcome to Aster.</h1>
          <p className="auth-help">Sign in or create an account to begin shaping your space.</p>
          {error && <p className="auth-error" role="alert">{error}</p>}
          {message && <p className="auth-ok" role="status">{message}</p>}
          <form className="form-grid">
            <input type="hidden" name="next" value={next} />
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" name="email" type="email" autoComplete="email" required maxLength={320} />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" autoComplete="current-password" required maxLength={256} />
              <small>Use at least 8 characters when creating an account.</small>
            </div>
            <button className="primary" formAction={signIn}>Sign in</button>
            <button className="soft" formAction={signUp}>Create account</button>
          </form>
        </div>
      </section>
    </main>
  );
}
