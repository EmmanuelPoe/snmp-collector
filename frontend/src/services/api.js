import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('snmp_access_token');
    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('snmp_access_token');
            window.location.href = '/login';
        }
        if (error.response?.status === 403 && error.response?.data?.detail === 'password_change_required') {
            window.location.href = '/change-password';
        }
        return Promise.reject(error);
    }
);

// ===== Devices =====
export const getDevices = async (enabledOnly = false) => {
    const response = await api.get('/devices', { params: { enabled_only: enabledOnly } });
    return response.data;
};
export const getDevice = async (deviceId) => {
    const response = await api.get(`/devices/${deviceId}`);
    return response.data;
};
export const createDevice = async (deviceData) => {
    const response = await api.post('/devices', deviceData);
    return response.data;
};
export const updateDevice = async (deviceId, deviceData) => {
    const response = await api.put(`/devices/${deviceId}`, deviceData);
    return response.data;
};
export const deleteDevice = async (deviceId) => {
    await api.delete(`/devices/${deviceId}`);
};
export const getDeviceCredentials = async (deviceId) => {
    const response = await api.get(`/devices/${deviceId}/credentials`);
    return response.data;
};
export const getDeviceTags = async () => {
    const response = await api.get('/devices/tags');
    return response.data;
};

// ===== Metrics =====
export const getMetrics = async (params = {}) => {
    const response = await api.get('/metrics', { params });
    return response.data;
};
export const getAvailableMetrics = async (deviceId) => {
    const response = await api.get(`/metrics/available/${deviceId}`);
    return response.data;
};
export const getLatestMetrics = async (deviceId, limit = 100) => {
    const response = await api.get(`/metrics/latest/${deviceId}`, { params: { limit } });
    return response.data;
};
export const getDeviceInterfaces = async (deviceId) => {
    const response = await api.get(`/metrics/interfaces/${deviceId}`);
    return response.data;
};
export const getInterfaceStats = async (deviceId, interfaceName, hours = 24) => {
    const response = await api.get(`/metrics/stats/${deviceId}/${interfaceName}`, { params: { hours } });
    return response.data;
};
export const getInterfaceRates = async (deviceId, hours = 1) => {
    const response = await api.get(`/metrics/rates/${deviceId}`, { params: { hours } });
    return response.data;
};
export const getTraps = async (params = {}) => {
    const response = await api.get('/metrics/traps', { params });
    return response.data;
};
export const exportDeviceCsv = async (deviceId, hours = 720) => {
    const response = await api.get(`/metrics/export/csv/${deviceId}`, { params: { hours }, responseType: 'blob' });
    return response;
};
export const getInterfaceHistory = async (deviceId, interfaceName, hours = 1, buckets = 60) => {
    const response = await api.get(`/metrics/history/${deviceId}`, {
        params: { interface_name: interfaceName, hours, buckets },
    });
    return response.data;
};
export const triggerCollection = async (deviceId) => {
    const response = await api.post(`/metrics/collect/${deviceId}`);
    return response.data;
};

// ===== Configuration =====
export const getModules = async () => {
    const response = await api.get('/config/modules');
    return response.data;
};
export const getConfigs = async () => {
    const response = await api.get('/config/configs');
    return response.data;
};
export const createConfig = async (configData) => {
    const response = await api.post('/config/configs', configData);
    return response.data;
};
export const updateConfig = async (configId, updates) => {
    const response = await api.put(`/config/configs/${configId}`, updates);
    return response.data;
};
export const deleteConfig = async (configId) => {
    await api.delete(`/config/configs/${configId}`);
};

// ===== MIB Browser (on-demand walk) =====
export const walkDevice = async (deviceId, baseOid = '1.3.6.1.2.1') => {
    const r = await api.post(`/devices/${deviceId}/walk`, null, { params: { base_oid: baseOid } });
    return r.data;
};
export const getWalkResult = async (commandId) => {
    const r = await api.get(`/devices/walk/${commandId}`);
    return r.data;
};

// ===== Notification Channels =====
export const getNotificationChannels = async () => {
    const response = await api.get('/notification-channels');
    return response.data;
};
export const createNotificationChannel = async (data) => {
    const response = await api.post('/notification-channels', data);
    return response.data;
};
export const updateNotificationChannel = async (channelId, updates) => {
    const response = await api.put(`/notification-channels/${channelId}`, updates);
    return response.data;
};
export const deleteNotificationChannel = async (channelId) => {
    await api.delete(`/notification-channels/${channelId}`);
};

// ===== Maintenance Windows =====
export const getMaintenanceWindows = async (activeOnly = false) => {
    const response = await api.get('/maintenance-windows', { params: { active_only: activeOnly } });
    return response.data;
};
export const createMaintenanceWindow = async (data) => {
    const response = await api.post('/maintenance-windows', data);
    return response.data;
};
export const deleteMaintenanceWindow = async (windowId) => {
    await api.delete(`/maintenance-windows/${windowId}`);
};

// ===== Auth =====
export const changePassword = async (currentPassword, newPassword) => {
    await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
    });
};
export const getUsers = async () => {
    const response = await api.get('/auth/users');
    return response.data;
};
export const registerUser = async (email, password, role) => {
    const response = await api.post('/auth/register', { email, password, role });
    return response.data;
};

// ===== Health Check =====
export const healthCheck = async () => {
    const response = await api.get('/health');
    return response.data;
};

// ===== Agents =====
export const getAgents = async () => {
    const response = await api.get('/agents');
    return response.data;
};
export const createAgentSlot = async (label) => {
    const response = await api.post('/agents/slots', { label });
    return response.data;
};
export const deleteAgentSlot = async (slotId) => {
    await api.delete(`/agents/slots/${slotId}`);
};
export const clearOfflineAgents = async () => {
    await api.delete('/agents');
};

// ===== Alerts =====
export const getAlerts = async (includeResolved = false) => {
    const response = await api.get('/alerts', { params: { include_resolved: includeResolved } });
    return response.data;
};
export const getAlertCount = async () => {
    const response = await api.get('/alerts/count');
    return response.data;
};
export const resolveAlert = async (alertId) => {
    const response = await api.put(`/alerts/${alertId}/resolve`);
    return response.data;
};
export const acknowledgeAlert = async (alertId) => {
    const response = await api.put(`/alerts/${alertId}/acknowledge`);
    return response.data;
};
export const assignAlert = async (alertId, assignedTo) => {
    const response = await api.put(`/alerts/${alertId}/assign`, { assigned_to: assignedTo });
    return response.data;
};
export const setAlertNote = async (alertId, note) => {
    const response = await api.put(`/alerts/${alertId}/note`, { note });
    return response.data;
};
export const getAssignableUsers = async () => {
    const response = await api.get('/auth/users/assignable');
    return response.data;
};
export const getAlertRules = async (deviceId) => {
    const response = await api.get(`/alert-rules/${deviceId}`);
    return response.data;
};
export const saveAlertRules = async (deviceId, rules) => {
    const response = await api.post(`/alert-rules/${deviceId}`, rules);
    return response.data;
};

export default api;

