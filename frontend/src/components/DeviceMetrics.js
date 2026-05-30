import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getDevices, getInterfaceRates } from '../services/api';
import InterfaceCard from './InterfaceCard';
import InterfacePanel from './InterfacePanel';

function DeviceMetrics() {
    const [searchParams] = useSearchParams();
    const [devices, setDevices] = useState([]);
    const [selectedDevice, setSelectedDevice] = useState('');
    const [ratesData, setRatesData] = useState(null);
    const [selectedIface, setSelectedIface] = useState(null);
    const [loading, setLoading] = useState(false);
    const intervalRef = useRef(null);

    useEffect(() => {
        loadDevices();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setRatesData(null);
        setSelectedIface(null);
        if (!selectedDevice) return;
        loadRates();
        intervalRef.current = setInterval(loadRates, 60000);
        return () => clearInterval(intervalRef.current);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedDevice]);

    const loadDevices = async () => {
        try {
            const data = await getDevices(true);
            setDevices(data);
            const paramId = searchParams.get('device_id');
            if (paramId) {
                const match = data.find(d => String(d.id) === String(paramId));
                if (match) setSelectedDevice(String(match.id));
            }
        } catch (err) {
            console.error('DeviceMetrics: failed to load devices', err);
        }
    };

    const loadRates = async () => {
        if (!selectedDevice) return;
        setLoading(true);
        try {
            const data = await getInterfaceRates(selectedDevice);
            setRatesData(data);
        } catch (err) {
            console.error('DeviceMetrics: failed to load rates', err);
        } finally {
            setLoading(false);
        }
    };

    const interfaces = ratesData ? Object.entries(ratesData.interfaces) : [];

    return (
        <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexShrink: 0 }}>
                <div className="page-title">Interface Monitor</div>
                <select className="select" value={selectedDevice} onChange={e => setSelectedDevice(e.target.value)} style={{ maxWidth: 300 }}>
                    <option value="">Select Device...</option>
                    {devices.map(d => (
                        <option key={d.id} value={d.id}>{d.name} ({d.ip_address})</option>
                    ))}
                </select>
                {selectedDevice && (
                    <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', color: '#10b981', padding: '3px 10px', borderRadius: 12, fontSize: 11 }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block', animation: 'pulse 1.5s infinite' }} />
                        Live · refreshes every 60s
                    </span>
                )}
            </div>
            <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
                <div style={{ position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, overflowY: 'auto', padding: '1.5rem' }}>
                    {!selectedDevice && <div className="text-muted" style={{ textAlign: 'center', marginTop: '3rem' }}>Select a device to begin monitoring.</div>}
                    {selectedDevice && loading && !ratesData && <div className="text-muted" style={{ textAlign: 'center', marginTop: '3rem' }}>Loading interfaces...</div>}
                    {ratesData && interfaces.length === 0 && (
                        <div className="text-muted" style={{ textAlign: 'center', marginTop: '3rem' }}>
                            No interfaces discovered yet.<br />The agent polls every 60 seconds — check back shortly.
                        </div>
                    )}
                    {interfaces.length > 0 && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
                            {interfaces.map(([iface, data]) => (
                                <InterfaceCard key={iface} deviceId={selectedDevice} iface={iface} data={data} isActive={selectedIface === iface} onClick={() => setSelectedIface(prev => prev === iface ? null : iface)} />
                            ))}
                        </div>
                    )}
                </div>
                {selectedIface && ratesData && (
                    <div style={{ position: 'absolute', top: 0, right: 0, bottom: 0, width: 480, zIndex: 10, boxShadow: '-4px 0 24px rgba(0,0,0,0.4)' }}>
                        <InterfacePanel deviceId={selectedDevice} iface={selectedIface} ifaceData={ratesData.interfaces[selectedIface]} onClose={() => setSelectedIface(null)} />
                    </div>
                )}
            </div>
        </div>
    );
}

export default DeviceMetrics;
