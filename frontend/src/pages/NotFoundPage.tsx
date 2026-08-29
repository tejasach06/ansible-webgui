import { PageHeader } from "../components/PageHeader";
import { Link } from "react-router-dom";
import { linkClass } from "../lib/cn";

export function NotFoundPage() {
  return (
    <section className="grid gap-4">
      <PageHeader title="Page not found" subtitle="Check the URL, or return to the dashboard." />
      <div>
        <Link className={linkClass} to="/">Go to dashboard</Link>
      </div>
    </section>
  );
}

export default NotFoundPage;
