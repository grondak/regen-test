FROM python:3.11-slim
WORKDIR /app
COPY pick_ticket_worker.py /app/pick_ticket_worker.py
COPY sqs_consumer.py /app/sqs_consumer.py
ENTRYPOINT ["python3", "/app/pick_ticket_worker.py"]
CMD ["pick-work-queue-url", "pick-tickets.txt", "--state-file", "pick-ticket-worker-state.json"]
