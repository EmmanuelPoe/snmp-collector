FROM alpine:latest

# Install snmpd (SNMP daemon)
RUN apk add --no-cache net-snmp net-snmp-tools

# Create config directory
RUN mkdir -p /etc/snmp

# Create snmpd configuration
RUN echo "# SNMPv2c configuration" > /etc/snmp/snmpd.conf && \
    echo "rocommunity public" >> /etc/snmp/snmpd.conf && \
    echo "agentAddress udp:161" >> /etc/snmp/snmpd.conf && \
    echo "sysLocation Simulated Network Device" >> /etc/snmp/snmpd.conf && \
    echo "sysContact Admin <admin@example.com>" >> /etc/snmp/snmpd.conf && \
    echo "sysDescr Simulated Router for Testing" >> /etc/snmp/snmpd.conf

EXPOSE 161/udp

CMD ["/usr/sbin/snmpd", "-f", "-Lo", "-C", "-c", "/etc/snmp/snmpd.conf"]
