import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// ===== Devices =====

export const getDevices = async (enabledOnly = false) => {
    const response = await api.get('/devices', {
        params: { enabled_only: enabledOnly }
    });
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
    const response = await api.get(`/metrics/latest/${deviceId}`, {
        params: { limit }
    });
    return response.data;
};

export const getDeviceInterfaces = async (deviceId) => {
    const response = await api.get(`/metrics/interfaces/${deviceId}`);
    return response.data;
};

export const getInterfaceStats = async (deviceId, interfaceName, hours = 24) => {
    const response = await api.get(`/metrics/stats/${deviceId}/${interfaceName}`, {
        params: { hours }
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

export const getModuleConfig = async (moduleName) => {
    const response = await api.get(`/config/modules/${moduleName}`);
    return response.data;
};

export const updateModuleConfig = async (moduleName, yamlContent) => {
    const response = await api.put(`/config/modules/${moduleName}`, { yaml_content: yamlContent });
    return response.data;
};

export const getSchedule = async (deviceId) => {
    const response = await api.get(`/config/schedule/${deviceId}`);
    return response.data;
};

export const updateSchedule = async (deviceId, scheduleData) => {
    const response = await api.put(`/config/schedule/${deviceId}`, scheduleData);
    return response.data;
};

export const createSchedule = async (scheduleData) => {
    const response = await api.post('/config/schedule', scheduleData);
    return response.data;
};

export const reloadConfig = async () => {
    const response = await api.post('/config/reload');
    return response.data;
};

// ===== Health Check =====

export const healthCheck = async () => {
    const response = await api.get('/health');
    return response.data;
};

export default api;
