# Wazuh OVA: Filebeat Configuration for Redis SIEM Pipeline

If you are using the official Wazuh OVA, it comes with Filebeat pre-installed and configured to send alerts directly to the built-in Wazuh Indexer (Elasticsearch) running on the same VM.

To reroute those alerts into your new Docker-based Redis buffer, you need to modify the Filebeat configuration on the OVA.

## Prerequisites
- SSH access to the Wazuh OVA (or access via the VM console).
- Root privileges (use `sudo` for editing configuration files).

## Step-by-Step Instructions

1. **Open the Filebeat configuration file:**
   ```bash
   sudo nano /etc/filebeat/filebeat.yml
   ```

2. **Disable the existing Elasticsearch Output:**
   Filebeat can only have one primary output active at a time. You must comment out the entire `output.elasticsearch` block.
   
   *Find and comment out these lines (add a `#` at the beginning of each line):*
   ```yaml
   #output.elasticsearch.hosts:
   #  - 127.0.0.1:9200
   
   #output.elasticsearch:
   #  protocol: https
   #  username: ${username}
   #  password: ${password}
   #  ssl.certificate_authorities:
   #    - /etc/filebeat/certs/root-ca.pem
   #  ssl.certificate: "/etc/filebeat/certs/wazuh-server.pem"
   #  ssl.key: "/etc/filebeat/certs/wazuh-server-key.pem"
   ```

3. **Disable Template and ILM Setup:**
   Since Filebeat is no longer communicating directly with Elasticsearch, it cannot manage index templates or ILM policies. (Our Logstash pipeline handles this automatically now).

   *Find and comment out these lines:*
   ```yaml
   #setup.template.json.enabled: true
   #setup.template.json.path: '/etc/filebeat/wazuh-template.json'
   #setup.template.json.name: 'wazuh'
   #setup.ilm.overwrite: true
   #setup.ilm.enabled: false
   ```

4. **Add the Redis Output:**
   Paste the following block immediately below the lines you just commented out. 
   
   **IMPORTANT:** Replace `YOUR_DOCKER_HOST_IP` with the actual IP address of the machine running your Redis Docker container. Keep the quotes around the IP and password.

   ```yaml
   output.redis:
     hosts: ["YOUR_DOCKER_HOST_IP:6379"]
     password: "12345678"
     key: "wazuh-alerts"
     data_type: list
   ```

5. **Save and Restart Filebeat:**
   - Save the file and exit the editor (in `nano`, press `Ctrl+O`, `Enter`, then `Ctrl+X`).
   - Restart the Filebeat service to apply the changes:
     ```bash
     sudo systemctl restart filebeat
     ```
   - Check the status to ensure it's running without errors:
     ```bash
     sudo systemctl status filebeat
     ```

## Verification
To confirm that the OVA is successfully sending alerts to your Redis buffer:
1. Ensure your Redis Docker container is running.
2. Log into the Docker host and check the queue length:
   ```bash
   docker exec -it redis-secured redis-cli -a 12345678 LLEN wazuh-alerts
   ```
3. Generate an alert on a Wazuh Agent (e.g., failed SSH login or RDP auth).
4. Run the `LLEN` command again. The number should increase, proving the OVA is successfully buffering data in Redis.

*Note: By disabling the Elasticsearch output in Filebeat, new alerts will no longer populate the built-in Wazuh Dashboard on the OVA. They will instead appear in your Docker Kibana instance once the full Logstash/Elasticsearch stack is running.*
