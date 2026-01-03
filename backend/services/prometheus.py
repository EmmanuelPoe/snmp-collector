import httpx
import yaml
import logging
from typing import Dict, List, Optional
from config import settings

logger = logging.getLogger(__name__)


async def query_snmp_exporter(target: str, module: str = "if_mib") -> Optional[str]:
    """
    Query the SNMP Exporter for metrics from a target device
    
    Args:
        target: IP address of the SNMP device
        module: SNMP module to use (default: if_mib)
    
    Returns:
        Prometheus metrics in text format, or None if error
    """
    url = f"{settings.snmp_exporter_url}/snmp"
    params = {
        "target": target,
        "module": module
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError as e:
        logger.error(f"Error querying SNMP Exporter for {target}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error querying SNMP Exporter: {str(e)}")
        return None


def parse_prometheus_metrics(metrics_text: str) -> List[Dict]:
    """
    Parse Prometheus text format metrics
    
    Args:
        metrics_text: Raw Prometheus metrics in text format
    
    Returns:
        List of parsed metrics as dictionaries
    """
    metrics = []
    
    for line in metrics_text.split('\n'):
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        
        try:
            # Parse metric line: metric_name{labels} value timestamp
            if '{' in line:
                # Extract metric name
                metric_name = line[:line.index('{')]
                
                # Extract labels
                labels_str = line[line.index('{')+1:line.index('}')]
                labels = {}
                for label_pair in labels_str.split(','):
                    if '=' in label_pair:
                        key, val = label_pair.split('=', 1)
                        labels[key.strip()] = val.strip('"')
                
                # Extract value (and optional timestamp)
                value_part = line[line.index('}')+1:].strip().split()
                value = float(value_part[0])
                
                metrics.append({
                    'metric_name': metric_name,
                    'labels': labels,
                    'value': value
                })
            else:
                # Simple metric without labels
                parts = line.split()
                if len(parts) >= 2:
                    metrics.append({
                        'metric_name': parts[0],
                        'labels': {},
                        'value': float(parts[1])
                    })
        except Exception as e:
            logger.warning(f"Error parsing metric line '{line}': {str(e)}")
            continue
    
    return metrics


def update_prometheus_config(devices: List[Dict]) -> bool:
    """
    Update Prometheus SNMP Exporter configuration file
    
    Args:
        devices: List of device configurations
    
    Returns:
        True if successful, False otherwise
    """
    try:
        config = {
            'if_mib': {
                'walk': [
                    '1.3.6.1.2.1.2.2.1.8',   # ifOperStatus
                    '1.3.6.1.2.1.2.2.1.10',  # ifInOctets
                    '1.3.6.1.2.1.2.2.1.16',  # ifOutOctets
                    '1.3.6.1.2.1.2.2.1.11',  # ifInUcastPkts
                    '1.3.6.1.2.1.2.2.1.17',  # ifOutUcastPkts
                    '1.3.6.1.2.1.31.1.1.1.1', # ifName
                ],
                'version': 2,
                'auth': {
                    'community': 'public'
                }
            }
        }
        
        # Write configuration file
        with open(settings.prometheus_config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        logger.info(f"Updated Prometheus config: {settings.prometheus_config_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating Prometheus config: {str(e)}")
        return False


async def reload_prometheus_config() -> bool:
    """
    Reload Prometheus SNMP Exporter configuration
    
    Note: The SNMP Exporter doesn't have a reload endpoint,
    so this is a placeholder. In production, you might need to
    restart the container or send a SIGHUP signal.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if exporter is healthy
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.snmp_exporter_url}/")
            response.raise_for_status()
            logger.info("SNMP Exporter is healthy")
            return True
    except Exception as e:
        logger.error(f"Error checking SNMP Exporter health: {str(e)}")
        return False
