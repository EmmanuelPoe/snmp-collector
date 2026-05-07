import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import DeviceManagement from './components/DeviceManagement';
import MetricsViewer from './components/MetricsViewer';
import ConfigurationManager from './components/ConfigurationManager';
import AgentsPage from './components/AgentsPage';
import LoginPage from './pages/LoginPage';
import PrivateRoute from './components/PrivateRoute';
import { useAuth } from './hooks/useAuth';
import './App.css';

function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  function handleLogout() { logout(); navigate('/login'); }
  return (
    <nav className="navbar">
      <div className="container">
        <div className="nav-brand"><h2>📊 SNMP Collector</h2></div>
        <div className="nav-links">
          <Link to="/" className="nav-link">Dashboard</Link>
          <Link to="/devices" className="nav-link">Devices</Link>
          <Link to="/metrics" className="nav-link">Metrics</Link>
          <Link to="/agents" className="nav-link">Agents</Link>
          <Link to="/config" className="nav-link">Configuration</Link>
          {user && <span style={{ marginLeft: '1rem', color: '#aaa' }}>{user.email}</span>}
          {user && <button onClick={handleLogout} style={{ marginLeft: '0.5rem' }}>Logout</button>}
        </div>
      </div>
    </nav>
  );
}

function App() {
  return (
    <Router>
      <div className="app">
        <NavBar />
        <main className="main-content">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
            <Route path="/devices" element={<PrivateRoute><DeviceManagement /></PrivateRoute>} />
            <Route path="/metrics" element={<PrivateRoute><MetricsViewer /></PrivateRoute>} />
            <Route path="/agents" element={<PrivateRoute><AgentsPage /></PrivateRoute>} />
            <Route path="/config" element={<PrivateRoute><ConfigurationManager /></PrivateRoute>} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
