# Product API Monitoring

Prometheus loads `product_api_alerts.yml` and scrapes the product API at
`api-server:8000/metrics`.

Alertmanager sends notifications to a generic paged webhook receiver. Operators
must mount the secret webhook URL at:

```text
/etc/alertmanager/paged-webhook-url
```

Keep the webhook URL out of git and out of rendered logs. The file should
contain only the HTTPS endpoint accepted by the paging provider or internal
notification bridge.

Before enabling hosted exposure, run a delivery smoke:

```bash
python3 tools/smoke_alert_delivery.py \
  --url-file /etc/alertmanager/paged-webhook-url \
  --out-json runs/alert_delivery_smoke_current.json
```

For CI or local plumbing checks without an external webhook:

```bash
python3 tools/smoke_alert_delivery.py --local-receiver-smoke
```
