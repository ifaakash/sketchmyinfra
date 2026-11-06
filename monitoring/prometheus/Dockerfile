FROM prom/prometheus
ENTRYPOINT [ "/bin/prometheus" ]

CMD ["--config.file=/etc/prometheus/prometheus.yml", "--storage.tsdb.path=/prometheus", "--web.enable-lifecycle"]
