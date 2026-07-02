export default function Spinner({ center }: { center?: boolean }) {
  const el = <div className="spinner" role="status" aria-label="Loading" />;
  return center ? <div className="spinner-center">{el}</div> : el;
}
