import type { ReactNode } from "react";

interface Props {
  id?: string; title: string; question?: string; right?: ReactNode; loading?: boolean; error?: string | null;
  empty?: { title: string; body: string } | null; foot?: ReactNode; className?: string; children?: ReactNode;
}

/** Panel shell: title + the one question the panel answers, loading/error/empty states.
 *  On error the last valid content stays visible with the error message above it. */
export function Panel({ id, title, question, right, loading, error, empty, foot, className, children }: Props) {
  return (
    <section id={id} className={`panel ${className ?? ""}`} aria-busy={loading || undefined}>
      <header className="panel-head">
        <div>
          <h2 className="panel-title">{title}</h2>
          {question && <div className="panel-q">{question}</div>}
        </div>
        {right}
      </header>
      {error && <div className="panel-error" role="alert">Could not refresh: {error}</div>}
      <div className="panel-body">
        {loading && <div className="loading-bar" aria-hidden />}
        {empty ? <div className="panel-state"><div><strong>{empty.title}</strong>{empty.body}</div></div> : children}
      </div>
      {foot && <footer className="panel-foot">{foot}</footer>}
    </section>
  );
}
