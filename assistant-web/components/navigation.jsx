import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["/assistant", "Today"],
  ["/assistant/talk", "Talk"],
  ["/assistant/plan", "Plan"],
  ["/assistant/reflections", "Reflect"],
  ["/assistant/money", "Money"],
  ["/assistant/guide", "Guide"],
  ["/assistant/personalize", "Personalize"],
];

export default function Navigation() {
  const pathname = usePathname();
  return <nav className="side-nav" aria-label="Main navigation">{links.map(([href, label]) => {
    const active = href === "/assistant" ? pathname === href : pathname === href || pathname.startsWith(href + "/");
    return <Link className={active ? "side-link active" : "side-link"} href={href} key={href}>{label}</Link>;
  })}</nav>;
}
