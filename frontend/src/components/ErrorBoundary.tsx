import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/** Catches render errors in a subtree so one bad panel degrades gracefully
 *  instead of white-screening the whole app. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep a console breadcrumb; the UI stays usable.
    console.error("Helix UI error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="empty">
          <div className="big">Something went wrong rendering this view</div>
          <div style={{ maxWidth: 420, marginTop: 6 }}>
            The rest of Helix is still fine — switch tabs, or reload. If it persists, the spec or
            a backend response may be malformed.
          </div>
          <button
            className="btn"
            style={{ marginTop: 16 }}
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
