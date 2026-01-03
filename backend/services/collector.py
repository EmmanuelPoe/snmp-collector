import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Device, CollectionSchedule, SNMPMetric, CollectionConfig
from services.prometheus import query_snmp_exporter, parse_prometheus_metrics

logger = logging.getLogger(__name__)


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
        
        # Query SNMP Exporter
        metrics_text = await query_snmp_exporter(device.ip_address, module="if_mib")
        if not metrics_text:
            logger.error(f"Failed to get metrics from {device.name}")
            return False
        
        # Parse metrics
        parsed_metrics = parse_prometheus_metrics(metrics_text)
        logger.info(f"Parsed {len(parsed_metrics)} metrics from {device.name}")
        
        # Store metrics in database
        timestamp = datetime.utcnow()
        stored_count = 0
        
        for metric in parsed_metrics:
            metric_name = metric['metric_name']
            labels = metric['labels']
            value = metric['value']
            
            # Extract interface information if available
            interface_name = labels.get('ifName', labels.get('ifDescr'))
            interface_index = labels.get('ifIndex')
            if interface_index:
                try:
                    interface_index = int(interface_index)
                except ValueError:
                    interface_index = None
            
            # Map metric names to OIDs (simplified)
            oid_mapping = {
                'ifOperStatus': '1.3.6.1.2.1.2.2.1.8',
                'ifInOctets': '1.3.6.1.2.1.2.2.1.10',
                'ifOutOctets': '1.3.6.1.2.1.2.2.1.16',
                'ifInUcastPkts': '1.3.6.1.2.1.2.2.1.11',
                'ifOutUcastPkts': '1.3.6.1.2.1.2.2.1.17',
            }
            
            # Determine OID
            oid = oid_mapping.get(metric_name, 'unknown')
            
            # Only store metrics we care about
            if oid != 'unknown':
                db_metric = SNMPMetric(
                    device_id=device.id,
                    timestamp=timestamp,
                    interface_name=interface_name,
                    interface_index=interface_index,
                    oid=oid,
                    oid_name=metric_name,
                    value=value,
                    value_type='gauge'
                )
                db.add(db_metric)
                stored_count += 1
        
        # Update last collection time
        schedule = db.query(CollectionSchedule).filter(
            CollectionSchedule.device_id == device_id
        ).first()
        if schedule:
            schedule.last_collection = timestamp
        
        db.commit()
        logger.info(f"Stored {stored_count} metrics for {device.name}")
        return True
        
    except Exception as e:
        logger.error(f"Error collecting metrics for device {device_id}: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()


async def run_scheduled_collection():
    """
    Background task to run scheduled metric collection for all enabled devices
    """
    logger.info("Starting scheduled collection service")
    
    while True:
        db = SessionLocal()
        try:
            # Get all enabled schedules
            schedules = db.query(CollectionSchedule).join(Device).filter(
                CollectionSchedule.enabled == True,
                Device.enabled == True
            ).all()
            
            for schedule in schedules:
                # Check if it's time to collect
                now = datetime.utcnow()
                
                if schedule.last_collection is None:
                    # First collection
                    should_collect = True
                else:
                    # Check if interval has elapsed
                    elapsed = (now - schedule.last_collection).total_seconds()
                    should_collect = elapsed >= schedule.interval_seconds
                
                if should_collect:
                    device = schedule.device
                    logger.info(f"Scheduled collection for {device.name}")
                    await collect_device_metrics(device.id)
            
        except Exception as e:
            logger.error(f"Error in scheduled collection: {str(e)}")
        finally:
            db.close()
        
        # Sleep for a short interval before checking again
        await asyncio.sleep(10)  # Check every 10 seconds


def start_background_collection():
    """
    Start the background collection service
    """
    logger.info("Background collection service initialized")
    # Note: This will be called from main.py using asyncio.create_task()
