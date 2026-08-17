import { PageHeader } from "../components/PageHeader";
import { InventoriesPanel } from "../components/InventoriesPanel";

export function InventoriesPage() {
  return (
    <section className="grid gap-4">
      <PageHeader
        title="Inventories"
        subtitle="Host inventories, shared across projects or owned by one."
      />
      <InventoriesPanel />
    </section>
  );
}

export default InventoriesPage;
