import Link from "next/link";
import { signIn, signUp } from "./actions";

const errors = {
  invalid_input: "Enter a valid email and password.",
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
    ? "Check your email for a confirmation link, then return here to sign in."
    : null;
  const next = typeof params?.next === "string" ? params.next : "/assistant";

  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand" href="/">Phillap Assistant</Link>
        <Link className="navlink" href="/">Home</Link>
      </header>
      <section className="auth-wrap">
        <div className="card">
          <p className="eyebrow">Secure sign in</p>
          <h1>Welcome back.</h1>
          <p className="help">Use your email and password to access your private workspace.</p>
          {error && <p className="notice error" role="alert">{error}</p>}
          {message && <p className="notice" role="status">{message}</p>}
          <form className="form">
            <input type="hidden" name="next" value={next} />
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" name="email" type="email" autoComplete="email" required maxLength={320} />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" autoComplete="current-password" required maxLength={256} />
            </div>
            <button formAction={signIn}>Sign in</button>
            <button className="secondary" formAction={signUp}>Create account</button>
          </form>
        </div>
      </section>
    </main>
  );
}
