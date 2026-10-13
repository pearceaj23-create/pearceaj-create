import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand" href="/">Phillap Assistant</Link>
        <Link className="navlink" href="/login">Sign in</Link>
      </header>
      <section className="hero">
        <p className="eyebrow">A separate private workspace</p>
        <h1>Your assistant, ready when you are.</h1>
        <p className="lede">
          Sign in to open your protected Phillap Assistant workspace. This web app is
          separate from the local Phillap desktop app.
        </p>
        <Link className="button" href="/login">Continue to sign in</Link>
      </section>
    </main>
  );
}
