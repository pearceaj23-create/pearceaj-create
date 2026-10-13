import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["/assistant", "Today", "◈"],
  ["/assistant/talk", "Talk", "✳"],
  ["/assistant/plan", "Plan", "↗"],
  ["/assistant/reflections", "Reflect", "◷"],
  ["/assistant/money", "Money", "◇"],
  ["/assistant/guide", "Guide", "?"],
  ["/assistant/personalize", "Personalize", "◎"],
];

export default function Navigation() {
  const pathname = usePathname();
  return <nav className="nav-list" aria-label="Main navigation">{links.map(([href, label, icon]) => {
    const active = href === "/assistant" ? pathname === href : pathname === href || pathname.startsWith(href + "/");
    return <Link className="nav-link" aria-current={active ? "page" : undefined} href={href} key={href}><span className="nav-icon" aria-hidden="true">{icon}</span>{label}</Link>;
  })}</nav>;
}
