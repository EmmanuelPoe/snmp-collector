import httpx
import yaml
import logging
import os
from typing import Dict, List, Optional, Any
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
        "module": module,
        "auth": "public_v2"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError as e:
        logger.error(f"Error querying SNMP Exporter for {target} (module {module}): {str(e)}")
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


def get_available_modules() -> List[str]:
    """
    Parse snmp.yml and return a list of available modules
    
    Returns:
        List of module names (strings)
    """
    try:
        if not os.path.exists(settings.prometheus_config_path):
            logger.error(f"Config file not found: {settings.prometheus_config_path}")
            return ["if_mib"]
            
        with open(settings.prometheus_config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        if not config or 'modules' not in config:
            return ["if_mib"]
            
        return list(config['modules'].keys())
        
    except Exception as e:
        logger.error(f"Error reading available modules: {str(e)}")
        return ["if_mib"]


def get_all_metric_oids() -> Dict[str, str]:
    """
    Parse snmp.yml and return a mapping of metric names to OIDs
    for ALL modules.
    
    Returns:
        Dictionary mapping {metric_name: oid}
    """
    oid_map = {}
    try:
        if not os.path.exists(settings.prometheus_config_path):
            return oid_map
            
        with open(settings.prometheus_config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        if not config or 'modules' not in config:
            return oid_map
            
        for module_name, module_cfg in config['modules'].items():
            if 'metrics' in module_cfg:
                for metric in module_cfg['metrics']:
                    name = metric.get('name')
                    oid = metric.get('oid')
                    if name and oid:
                        oid_map[name] = oid
                        
        return oid_map
        
    except Exception as e:
        logger.error(f"Error reading metric OIDs: {str(e)}")
        return oid_map


def get_module_config(module_name: str) -> Optional[str]:
    """
    Get the YAML configuration for a specific module
    
    Args:
        module_name: Name of the module to retrieve
        
    Returns:
        YAML string of the module configuration or None if not found
    """
    try:
        if not os.path.exists(settings.prometheus_config_path):
            return None
            
        with open(settings.prometheus_config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        if not config or 'modules' not in config or module_name not in config['modules']:
            return None
            
        return yaml.dump(config['modules'][module_name], default_flow_style=False)
        
    except Exception as e:
        logger.error(f"Error getting module config: {str(e)}")
        return None


def validate_module_yaml(yaml_content: str) -> Dict[str, Any]:
    """
    Validate that the string is valid YAML and has basic required structure
    
    Args:
        yaml_content: The YAML string to validate
        
    Returns:
        Parsed dictionary if valid
        
    Raises:
        ValueError: If invalid
    """
    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML syntax: {str(e)}")
        
    if not isinstance(parsed, dict):
        raise ValueError("Module configuration must be a dictionary")
        
    # Basic structural check (a module typically has 'walk' or 'metrics', but strict requirement depends on use case)
    # For snmp exporter, 'walk' is common but might be empty. 'metrics' is common.
    # We'll just enforce it's a dict for now to allow flexibility, but could add stricter checks.
    
    return parsed


def update_module_config(module_name: str, yaml_content: str) -> bool:
    """
    Update a specific module's configuration in snmp.yml
    
    Args:
        module_name: Name of the module to update
        yaml_content: New YAML content for the module
        
    Returns:
        True if successful
        
    Raises:
        ValueError: If validation fails
        IOError: If file operations fail
    """
    # 1. Validate Input
    new_module_config = validate_module_yaml(yaml_content)
    
    try:
        # 2. Read Existing Config
        config = {}
        if os.path.exists(settings.prometheus_config_path):
            with open(settings.prometheus_config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
        
        # Ensure structure
        if 'modules' not in config:
            config['modules'] = {}
            
        # 3. Update the specific module
        config['modules'][module_name] = new_module_config
        
        # 4. Write back safely
        # We could write to a temp file first, but for simplicity we'll overwrite since we validated the chunk.
        # Ideally, we should validate the WHOLE file before saving, but yaml.dump guarantees valid syntax.
        
        with open(settings.prometheus_config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            
        logger.info(f"Updated configuration for module '{module_name}'")
        return True
        
    except Exception as e:
        logger.error(f"Error updating module config: {str(e)}")
        raise e


async def reload_prometheus_config() -> bool:
    """
    Reload Prometheus SNMP Exporter configuration via HTTP endpoint
    
    Returns:
        True if successful, False otherwise
    """
    url = f"{settings.snmp_exporter_url}/-/reload"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url)
            
            if response.status_code == 200:
                logger.info("Successfully reloaded SNMP Exporter configuration")
                return True
            else:
                logger.error(f"Failed to reload SNMP Exporter config. Status: {response.status_code}, Body: {response.text}")
                return False
                
    except httpx.HTTPError as e:
        logger.error(f"HTTP error reloading SNMP Exporter config: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error reloading SNMP Exporter config: {str(e)}")
        return False
