import os

import pika
import json

from dotenv import load_dotenv


# Load environment variables.
load_dotenv()

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
RABBITMQ_PORT = os.getenv('RABBITMQ_PORT')
RABBITMQ_USER = os.getenv('RABBITMQ_USER')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS')

RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE')
RABBITMQ_EXCHANGE = os.getenv('RABBITMQ_EXCHANGE')
RABBITMQ_ROUTING_KEY = os.getenv('RABBITMQ_ROUTING_KEY')


def process_message(message):
    # Simulate some processing
    print("Processing question:", message['question'])
    processed_message = {"processed": True, "answer": "some answer", "original_message": message}
    return processed_message


def callback(ch, method, properties, body):
    # Deserialize and process the message
    message = json.loads(body)
    processed_message = process_message(message)

    # Send the response back to the reply_to queue if it exists
    if properties.reply_to:
        ch.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            body=json.dumps(processed_message),
            properties=pika.BasicProperties(correlation_id=properties.correlation_id)
        )

    # Acknowledge the message
    ch.basic_ack(delivery_tag=method.delivery_tag)


def consume_messages():
    credentials = pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials)
    connection = pika.BlockingConnection(parameters)

    channel = connection.channel()

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

    print("Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()


if __name__ == "__main__":
    consume_messages()

