import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import EmptyState from '../components/EmptyState';

export default function Transactions() {
  return (
    <div>
      <PageHeader title="Transactions" subtitle="Filterable history across all accounts" />
      <Card>
        <EmptyState title="Coming in the next pass" hint="This page will land with filters, charts, and a sortable table." />
      </Card>
    </div>
  );
}
