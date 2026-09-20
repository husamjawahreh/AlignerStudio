interface UnavailableStateProps {
  title: string;
  message: string;
}

export function UnavailableState({ title, message }: UnavailableStateProps): JSX.Element {
  return (
    <div className="unavailable-state" role="status">
      <span className="unavailable-mark">!</span>
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}
