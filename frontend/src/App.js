import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import DeviceManagement from './components/DeviceManagement';
import DeviceMetrics from './components/DeviceMetrics';
import ConfigurationManager from './components/ConfigurationManager';
import AgentsPage from './components/AgentsPage';
import LoginPage from './pages/LoginPage';
import ChangePasswordPage from './pages/ChangePasswordPage';
import PrivateRoute from './components/PrivateRoute';
import Sidebar from './components/Sidebar';
import { ToastProvider } from './hooks/useToast';
import './App.css';

function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <div className="page-content">
          <Routes>
            <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
            <Route path="/devices" element={<PrivateRoute><DeviceManagement /></PrivateRoute>} />
            <Route path="/metrics" element={<PrivateRoute><DeviceMetrics /></PrivateRoute>} />
            <Route path="/agents" element={<PrivateRoute><AgentsPage /></PrivateRoute>} />
            <Route path="/config" element={<PrivateRoute><ConfigurationManager /></PrivateRoute>} />
          </Routes>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/change-password" element={<ChangePasswordPage />} />
          <Route path="/*" element={<AppShell />} />
        </Routes>
      </Router>
    </ToastProvider>
  );
}
