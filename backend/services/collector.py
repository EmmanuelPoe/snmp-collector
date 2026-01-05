import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Device, CollectionSchedule, SNMPMetric, IfMibMetric, CollectionConfig
from services.prometheus import query_snmp_exporter, parse_prometheus_metrics, get_all_metric_oids

logger = logging.getLogger(__name__)


def to_snake_case(name: str) -> str:
    """Convert camelCase to snake_case"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


async def collect_device_metrics(device_id: int) -> bool:
    """
    Collect SNMP metrics for a specific device
    
    Args:
        device_id: ID of the device to collect metrics from
    
    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    
    try:
        # Get device
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device or not device.enabled:
            logger.warning(f"Device {device_id} not found or disabled")
            return False
        
        logger.info(f"Collecting metrics for device: {device.name} ({device.ip_address})")
        
        # Get all metric OID mappings once for this run
        oid_map = get_all_metric_oids()
        
        # Determine modules to query
        modules_to_query = device.snmp_modules if device.snmp_modules else ["if_mib"]
        total_stored = 0
        
        for module in modules_to_query:
            logger.info(f"Querying module '{module}' for {device.name}")
            
            # Query SNMP Exporter
            metrics_text = await query_snmp_exporter(device.ip_address, module=module)
            if not metrics_text:
                logger.error(f"Failed to get metrics from {device.name} for module {module}")
                continue
            
            # Parse metrics
            parsed_metrics = parse_prometheus_metrics(metrics_text)
            logger.info(f"Parsed {len(parsed_metrics)} metrics from {device.name} (module: {module})")
            
            timestamp = datetime.now(timezone.utc)
            
            # --- IF_MIB SPECIAL HANDLING ---
            if module == 'if_mib':
                # Group by interface index
                interface_metrics: Dict[int, Dict[str, Any]] = {}
                
                for metric in parsed_metrics:
                    metric_name = metric['metric_name']
                    labels = metric['labels']
                    value = metric['value']
                    
                    # Skip internal metrics
                    if metric_name.startswith('scrape_') or metric_name == 'up':
                        continue
                        
                    # Extract Interface Info
                    if_index = labels.get('ifIndex')
                    if_name = labels.get('ifName', labels.get('ifDescr'))
                    
                    if not if_index:
                        continue
                        
                    try:
                        if_index = int(if_index)
                    except ValueError:
                        continue
                        
                    # Initialize dict for this interface if needed
                    if if_index not in interface_metrics:
                        interface_metrics[if_index] = {
                            'device_id': device.id,
                            'timestamp': timestamp,
                            'interface_index': if_index,
                            'interface_name': if_name
                        }
                    
                    # Map standard metric names to column names
                    # e.g. ifInOctets -> if_in_octets
                    col_name = to_snake_case(metric_name)
                    
                    # We only care about columns that exist in our model
                    # IfMibMetric has specific columns. We can use hasattr(IfMibMetric, col_name) check
                    # but simpler is just to try to add broadly or map specifically.
                    # snake_case mapping covers most (ifInOctets -> if_in_octets).
                    # 'ifHCInOctets' -> if_hc_in_octets.
                    
                    interface_metrics[if_index][col_name] = value

                # Batch insert for if_mib
                count = 0
                for if_idx, data in interface_metrics.items():
                    # Filter data to only include valid columns for safety
                    # (SQLAlchemy would error on extra keys)
                    valid_data = {}
                    for k, v in data.items():
                        if hasattr(IfMibMetric, k):
                            valid_data[k] = v
                    
                    if valid_data:
                        db_metric = IfMibMetric(**valid_data)
                        db.add(db_metric)
                        count += 1
                
                total_stored += count
                
            else:
                # --- GENERIC HANDLING FOR OTHER MODULES ---
                stored_count = 0
                for metric in parsed_metrics:
                    metric_name = metric['metric_name']
                    # ... [Standard generic processing] ...
                    # To keep it simple for this task, I will use a simplified version of previous logic
                    if metric_name.startswith('scrape_') or metric_name == 'up':
                        continue
                        
                    labels = metric['labels']
                    interface_name = labels.get('ifName', labels.get('ifDescr'))
                    interface_index = labels.get('ifIndex')
                    try:
                        if interface_index: interface_index = int(interface_index)
                    except: interface_index = None

                    oid = oid_map.get(metric_name) or metric_name
                    
                    db_metric = SNMPMetric(
                        device_id=device.id,
                        timestamp=timestamp,
                        module=module,
                        interface_name=interface_name,
                        interface_index=interface_index,
                        oid=oid,
                        oid_name=metric_name,
                        value=metric['value'],
                        value_type='gauge'
                    )
                    db.add(db_metric)
                    stored_count += 1
                total_stored += stored_count
            
        # Update last collection time
        schedule = db.query(CollectionSchedule).filter(
            CollectionSchedule.device_id == device_id
        ).first()
        if schedule:
            schedule.last_collection = datetime.now(timezone.utc)
        
        db.commit()
        logger.info(f"Stored metrics for {device.name}")
        return True
        
    except Exception as e:
        logger.error(f"Error collecting metrics for device {device_id}: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()


async def run_scheduled_collection():
    """Background task to run scheduled metric collection"""
    logger.info("Starting scheduled collection service")
    while True:
        db = SessionLocal()
        try:
            schedules = db.query(CollectionSchedule).join(Device).filter(
                CollectionSchedule.enabled == True,
                Device.enabled == True
            ).all()
            for schedule in schedules:
                now = datetime.now(timezone.utc)
                if schedule.last_collection is None:
                    should_collect = True
                else:
                    elapsed = (now - schedule.last_collection).total_seconds()
                    should_collect = elapsed >= schedule.interval_seconds
                
                if should_collect:
                    await collect_device_metrics(schedule.device.id)
        except Exception as e:
            logger.error(f"Error in scheduled collection: {str(e)}")
        finally:
            db.close()
        await asyncio.sleep(10)


def start_background_collection():
    logger.info("Background collection service initialized")
