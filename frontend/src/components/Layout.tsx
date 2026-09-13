import { Link, Outlet } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          Split<span>Easy</span>
        </Link>
        <div className="topbar-user">
          <span className="avatar" aria-hidden>
            {user?.username.charAt(0).toUpperCase()}
          </span>
          <span className="topbar-name">{user?.username}</span>
          <button className="btn btn-ghost btn-small" onClick={() => void logout()}>
            Log out
          </button>
        </div>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </div>
  );
}
