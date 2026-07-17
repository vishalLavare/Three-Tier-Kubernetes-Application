import { useState, useEffect, useCallback } from 'react';

interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  created_at?: string;
}

function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('User');
  const [editingId, setEditingId] = useState<number | null>(null);
  
  // Status & stats states
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [dbStatus, setDbStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [pingLatency, setPingLatency] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Read environment variable with absolute fallback or relative routing.
  // In production K8s, sharing the ingress makes '/api' absolute-relative to the host.
  const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '') + '/api';

  // Show a status notification
  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => {
      setNotification(null);
    }, 4000);
  };

  // Check health of backend & database
  const checkHealth = useCallback(async () => {
    const startTime = performance.now();
    try {
      const response = await fetch(`${API_BASE}/health`);
      const latency = Math.round(performance.now() - startTime);
      setPingLatency(latency);
      
      if (response.ok) {
        setBackendStatus('online');
        setDbStatus('connected');
      } else if (response.status === 503) {
        // Backend up, but Postgres connection failed
        setBackendStatus('online');
        setDbStatus('disconnected');
      } else {
        setBackendStatus('online');
        setDbStatus('disconnected');
      }
    } catch (error) {
      setBackendStatus('offline');
      setDbStatus('disconnected');
      setPingLatency(null);
      console.error('Health check failed:', error);
    }
  }, [API_BASE]);

  // Fetch users list
  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users`);
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      } else {
        showNotification('Failed to retrieve users', 'error');
      }
    } catch (error) {
      console.error('Error fetching users:', error);
      showNotification('Could not connect to user database API', 'error');
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  // Run checks on mount and intervals
  useEffect(() => {
    checkHealth();
    fetchUsers();

    const healthInterval = setInterval(checkHealth, 10000); // Check health every 10s
    return () => clearInterval(healthInterval);
  }, [checkHealth, fetchUsers]);

  // Handle Form submit (Create or Update)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email) {
      showNotification('Please fill in name and email', 'error');
      return;
    }

    setLoading(true);
    try {
      if (editingId !== null) {
        // Update request
        const response = await fetch(`${API_BASE}/users/${editingId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, role }),
        });

        if (response.ok) {
          showNotification('User updated successfully!');
          resetForm();
          fetchUsers();
          checkHealth();
        } else {
          const errData = await response.json();
          showNotification(errData.detail || 'Failed to update user', 'error');
        }
      } else {
        // Create request
        const response = await fetch(`${API_BASE}/users`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, role }),
        });

        if (response.ok) {
          showNotification('User created successfully!');
          resetForm();
          fetchUsers();
          checkHealth();
        } else {
          const errData = await response.json();
          showNotification(errData.detail || 'Failed to create user', 'error');
        }
      }
    } catch (error) {
      console.error('Error submitting form:', error);
      showNotification('Error connecting to backend API', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Trigger Edit mode
  const handleEdit = (user: User) => {
    setEditingId(user.id);
    setName(user.name);
    setEmail(user.email);
    setRole(user.role);
  };

  // Handle Delete
  const handleDelete = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this user?')) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/${id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        showNotification('User deleted successfully');
        fetchUsers();
        checkHealth();
      } else {
        showNotification('Failed to delete user', 'error');
      }
    } catch (error) {
      console.error('Error deleting user:', error);
      showNotification('Error connecting to backend API', 'error');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setEditingId(null);
    setName('');
    setEmail('');
    setRole('User');
  };

  return (
    <div className="app-container">
      {/* Glow effects */}
      <div className="glow-sphere-1"></div>
      <div className="glow-sphere-2"></div>

      {/* Header */}
      <header className="app-header">
        <div className="header-brand">
          <span className="brand-icon">⚓</span>
          <h1>Kubernetes Cloud-Native Portal</h1>
        </div>
        <div className="header-meta">
          <span className="badge-k8s">K8s Cluster Node</span>
          <button className="btn-refresh" onClick={() => { fetchUsers(); checkHealth(); }} disabled={loading}>
            {loading ? 'Refreshing...' : '🔄 Sync Grid'}
          </button>
        </div>
      </header>

      {/* Notification Toast */}
      {notification && (
        <div className={`toast-notification ${notification.type}`}>
          <div className="toast-content">
            <span className="toast-icon">{notification.type === 'success' ? '✅' : '❌'}</span>
            <span className="toast-message">{notification.message}</span>
          </div>
        </div>
      )}

      {/* Main Grid */}
      <main className="dashboard-grid">
        
        {/* Row 1: System Status Cards */}
        <section className="status-container">
          <div className="status-card glass">
            <h3>Frontend (Vite + React)</h3>
            <div className="status-indicator">
              <span className="status-dot online"></span>
              <span>Running (Production)</span>
            </div>
            <p className="card-desc">Served via NGINX Multi-stage Alpine container</p>
          </div>

          <div className="status-card glass">
            <h3>Backend API (FastAPI)</h3>
            <div className="status-indicator">
              <span className={`status-dot ${backendStatus}`}></span>
              <span>
                {backendStatus === 'online' && 'Online'}
                {backendStatus === 'checking' && 'Checking...'}
                {backendStatus === 'offline' && 'Offline'}
              </span>
            </div>
            <p className="card-desc">
              API latency: {pingLatency !== null ? `${pingLatency}ms` : 'N/A'}
            </p>
          </div>

          <div className="status-card glass">
            <h3>Database (PostgreSQL)</h3>
            <div className="status-indicator">
              <span className={`status-dot ${dbStatus === 'connected' ? 'online' : dbStatus === 'checking' ? 'checking' : 'offline'}`}></span>
              <span>
                {dbStatus === 'connected' && 'Connected'}
                {dbStatus === 'checking' && 'Connecting...'}
                {dbStatus === 'disconnected' && 'Disconnected'}
              </span>
            </div>
            <p className="card-desc">Persistent Volume Claim mounted storage</p>
          </div>
        </section>

        {/* Row 2: Management Panel & User List */}
        <div className="split-view">
          
          {/* Section: CRUD Form */}
          <section className="panel-card glass form-panel">
            <h2>{editingId !== null ? '✏️ Edit Cluster User' : '➕ Provision New User'}</h2>
            <p className="panel-subtitle">
              {editingId !== null ? 'Modify existing user parameters' : 'Register a new database user identity'}
            </p>

            <form onSubmit={handleSubmit} className="custom-form">
              <div className="form-group">
                <label>Full Name</label>
                <input
                  type="text"
                  placeholder="e.g. John Doe"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>

              <div className="form-group">
                <label>Email Address</label>
                <input
                  type="email"
                  placeholder="e.g. john.doe@kubernetes.io"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>

              <div className="form-group">
                <label>System Role</label>
                <select value={role} onChange={(e) => setRole(e.target.value)} disabled={loading}>
                  <option value="User">User</option>
                  <option value="Developer">Developer</option>
                  <option value="Manager">Manager</option>
                  <option value="Administrator">Administrator</option>
                </select>
              </div>

              <div className="form-actions">
                <button type="submit" className="btn-primary" disabled={loading}>
                  {editingId !== null ? 'Apply Changes' : 'Provision User'}
                </button>
                {editingId !== null && (
                  <button type="button" className="btn-secondary" onClick={resetForm} disabled={loading}>
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </section>

          {/* Section: Users Table */}
          <section className="panel-card glass table-panel">
            <div className="panel-header-row">
              <div>
                <h2>👥 Database Records</h2>
                <p className="panel-subtitle">Live users query from PostgreSQL backend</p>
              </div>
              <span className="badge-count">{users.length} Users</span>
            </div>

            <div className="table-responsive">
              {loading && users.length === 0 ? (
                <div className="table-loading">Querying Pod database...</div>
              ) : users.length === 0 ? (
                <div className="table-empty">
                  <span className="empty-icon">📁</span>
                  <p>No user records found in PostgreSQL.</p>
                  <button className="btn-secondary btn-sm" onClick={() => {
                    setName('Mock Tester');
                    setEmail(`mock-${Date.now()}@k8s.org`);
                    setRole('Developer');
                  }}>Fill Sample Info</button>
                </div>
              ) : (
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.id} className="table-row-animate">
                        <td><span className="user-id">#{user.id}</span></td>
                        <td><strong>{user.name}</strong></td>
                        <td>{user.email}</td>
                        <td>
                          <span className={`role-badge ${user.role.toLowerCase()}`}>
                            {user.role}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <div className="action-buttons">
                            <button
                              className="btn-action edit"
                              title="Edit user"
                              onClick={() => handleEdit(user)}
                              disabled={loading}
                            >
                              ✏️
                            </button>
                            <button
                              className="btn-action delete"
                              title="Delete user"
                              onClick={() => handleDelete(user.id)}
                              disabled={loading}
                            >
                              🗑️
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>

        </div>
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <p>Three-Tier Kubernetes Application &copy; 2026. Made with React, FastAPI, & PostgreSQL.</p>
        <div className="footer-links">
          <span>Namespace: <code>three-tier-app</code></span>
          <span>•</span>
          <span>Health check: <a href={`${API_BASE}/health`} target="_blank" rel="noreferrer">/api/health</a></span>
        </div>
      </footer>
    </div>
  );
}

export default App;
