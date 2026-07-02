import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import EmptyState from '../components/EmptyState';

// Shared placeholder for pages built in Phase 2. Renders in the new theme so the
// whole app looks consistent while individual pages are still being built out.
export default function Placeholder({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} />
      <Card>
        <EmptyState title="Coming in the next pass" hint="This page is being rebuilt with the new design system." />
      </Card>
    </div>
  );
}
