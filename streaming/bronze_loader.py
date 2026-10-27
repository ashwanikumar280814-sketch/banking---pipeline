import pg8000.dbapi
from kafka import KafkaConsumer

conn = pg8000.dbapi.connect(
    host="localhost", port=5432,
    database="warehouse", user="bank", password="bank123",
)
cur = conn.cursor()

cur.execute("CREATE SCHEMA IF NOT EXISTS bronze")
cur.execute("""
    CREATE TABLE IF NOT EXISTS bronze.raw_events (
        topic        TEXT   NOT NULL,
        partition    INT    NOT NULL,
        kafka_offset BIGINT NOT NULL,
        event_key    TEXT,
        payload      JSONB,
        ingested_at  TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (topic, partition, kafka_offset)
    )
""")
conn.commit()

consumer = KafkaConsumer(
    bootstrap_servers="localhost:9092",
    group_id="bronze-loader",
    auto_offset_reset="earliest",
    enable_auto_commit=False,
    consumer_timeout_ms=15000,
)
consumer.subscribe(pattern=r"^bank\.public\..*")

count = 0
for msg in consumer:
    key = msg.key.decode("utf-8") if msg.key else None
    val = msg.value.decode("utf-8") if msg.value else None
    cur.execute(
        """INSERT INTO bronze.raw_events
           (topic, partition, kafka_offset, event_key, payload)
           VALUES (%s, %s, %s, %s, %s::jsonb)
           ON CONFLICT DO NOTHING""",
        (msg.topic, msg.partition, msg.offset, key, val),
    )
    count += 1
    if count % 500 == 0:
        conn.commit()
        consumer.commit()
        print(f"{count} events saved...")

conn.commit()
consumer.commit()
cur.close()
conn.close()
print(f"Done. {count} events saved to bronze.raw_events")