import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import DeviceManagement from './components/DeviceManagement';
import MetricsViewer from './components/MetricsViewer';
import ConfigurationManager from './components/ConfigurationManager';
import AgentsPage from './components/AgentsPage';
import './App.css';

function App() {
    return (
        <Router>
            <div className="app">
                <nav className="navbar">
                    <div className="container">
                        <div className="nav-brand">
                            <h2>📊 SNMP Collector</h2>
                        </div>
                        <div className="nav-links">
                            <Link to="/" className="nav-link">Dashboard</Link>
                            <Link to="/devices" className="nav-link">Devices</Link>
                            <Link to="/metrics" className="nav-link">Metrics</Link>
                            <Link to="/agents" className="nav-link">Agents</Link>
                            <Link to="/config" className="nav-link">Configuration</Link>
                        </div>
                    </div>
                </nav>

                <main className="main-content">
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/devices" element={<DeviceManagement />} />
                        <Route path="/metrics" element={<MetricsViewer />} />
                        <Route path="/agents" element={<AgentsPage />} />
                        <Route path="/config" element={<ConfigurationManager />} />
                    </Routes>
                </main>
            </div>
        </Router>
    );
}

export default App;
