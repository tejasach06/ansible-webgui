import { PageHeader } from "../components/PageHeader";

export function NotFoundPage() {
  return (
    <section className="grid gap-4">
      <PageHeader title="Page not found" subtitle="Check the URL, or return to the dashboard." />
    </section>
  );
}

export default NotFoundPage;
