FROM prom/snmp-exporter:latest

# Copy custom configuration
COPY snmp.yml /etc/snmp_exporter/snmp.yml

# Expose SNMP Exporter port
EXPOSE 9116

# Use default entrypoint and command from base image
